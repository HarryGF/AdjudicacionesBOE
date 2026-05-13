import io
import json
import csv
import os
import re
import requests
import pdfplumber

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN Y PATRONES
# ══════════════════════════════════════════════════════════════════════════════
PATRONES_METADATOS = {
    "Objeto": r"(?i)Objeto:\s*(.*?)(?=Expediente:|$)",
    "Expediente": r"(?i)Expediente:\s*(.*?)(?=\s*\d+\.\s+[A-Z]|$)"
}

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE SOPORTE
# ══════════════════════════════════════════════════════════════════════════════
def codigos_objetivo(ruta_csv):
    cpvs_objetivo = set()
    try:
        with open(ruta_csv, "r", encoding="utf-8") as f:
            lector = csv.reader(f)
            next(lector, None)
            for fila in lector:
                if not fila:
                    continue
                codigo = fila[0].split('-')[0].strip()
                if len(codigo) == 8 and codigo.isdigit():
                    cpvs_objetivo.add(codigo)
        print(f"Cargados {len(cpvs_objetivo)} códigos CPV de interés.")
        return cpvs_objetivo
    except FileNotFoundError:
        print("Error: Archivo CSV de CPV no encontrado.")
        return set()
    except Exception as e:
        print(f"Error al cargar CSV: {e}")
        return set()

def dividir_por_lotes(texto_bloque, num_seccion):
    """
    Busca patrones tipo "12.1) Lote 1:" o "13.2) Lote 2:" y divide el texto.
    Si no hay lotes, devuelve todo el bloque bajo la clave 'General'.
    """
    patron_lote = rf"{num_seccion}\.\d+\)\s*Lote\s*([a-zA-Z0-9_]+):?"
    iterador = list(re.finditer(patron_lote, texto_bloque, re.IGNORECASE))
    
    if not iterador:
        return {"General": texto_bloque}
        
    lotes = {}
    for i, match in enumerate(iterador):
        nombre_lote = f"Lote {match.group(1).strip()}"
        inicio = match.end()
        fin = iterador[i+1].start() if i + 1 < len(iterador) else len(texto_bloque)
        lotes[nombre_lote] = texto_bloque[inicio:fin] 
    return lotes

def limpiar_basura_boe(texto):
    patron_basura = r"BOLETÍN OFICIAL DEL ESTADO.*?elbacifireV\s*"
    return re.sub(patron_basura, "", texto)

def descargar_y_extraer_texto(url_pdf):
    """Descarga el PDF y devuelve el texto normalizado en una sola línea."""
    res = requests.get(url_pdf, timeout=15)
    res.raise_for_status()
    with pdfplumber.open(io.BytesIO(res.content)) as pdf:
        texto = " ".join((p.extract_text() or "") for p in pdf.pages)
        return re.sub(r'\s+', ' ', texto)

# --- NUEVA FUNCIÓN PARA EXPORTAR CSV ---
def exportar_a_csv(lista_diccionarios, columnas, nombre_archivo):
    os.makedirs("Adjudicaciones_Filtradas", exist_ok=True)
    ruta = f"Adjudicaciones_Filtradas/{nombre_archivo}.csv"
    with open(ruta, "w", encoding="utf-8-sig", newline='') as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(lista_diccionarios)
    print(f"Archivo creado: {ruta}")

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE EXTRACCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def extraer_metadatos(texto):
    res = {}
    for campo, patron in PATRONES_METADATOS.items():
        match = re.search(patron, texto)
        res[campo] = match.group(1).strip() if match else ""
    return res

def extraer_adjudicatarios(texto_completo, lista_lotes):
    """
    Devuelve:
      resultados -> { lote_nombre: { NIF: { campos... } } }
      lista_nif  -> [ NIF, ... ]  (uno por lote, en el mismo orden)
    """
    patron_bloque = r"12\.\s*Adjudicatarios:(.*?)(?=13\.\s+Valor|$)"
    match_bloque = re.search(patron_bloque, texto_completo)
    if not match_bloque: 
        return {}, []

    bloque12 = limpiar_basura_boe(match_bloque.group(1))
    trozos_lotes = dividir_por_lotes(bloque12, "12")
    
    sig_campo = r"(?=\s*\d+\.(?:\d+\.)*\d+\)|$)" 
    resultados = {}

    for lote_nombre, chunk in trozos_lotes.items():
        if lote_nombre in lista_lotes:
            continue

        m_nom = re.search(r"12\.[0-9]*\.*[0-9]*\)\sNombre:\s*(.*?)\." + sig_campo, chunk)
        m_nif = re.search(r"Número de identificación fiscal:\s*([A-Z0-9]+)", chunk)
        m_dir = re.search(r"Dirección:\s*(.*?)\." + sig_campo, chunk)
        m_loc = re.search(r"Localidad:\s*(.*?)\." + sig_campo, chunk)
        m_cp  = re.search(r"Código postal:\s*(\d+)", chunk)
        m_pais = re.search(r"País:\s*(.*?)\." + sig_campo, chunk)
        
        nif = m_nif.group(1).strip() if m_nif else "SIN_NIF"

        datos = {
            "Nombre Adjudicatario": m_nom.group(1).strip() if m_nom else "",
            "NIF": nif,
            "Direccion": m_dir.group(1).strip() if m_dir else "No disponible",
            "Localidad": m_loc.group(1).strip() if m_loc else "",
            "Codigo Postal": m_cp.group(1).strip() if m_cp else "",
            "Pais": m_pais.group(1).strip() if m_pais else ""
        }
        
        datos["PYME"] = "si" if "es una pyme" in chunk.lower() and "no es" not in chunk.lower() else "no"
        resultados[lote_nombre] = datos

    return resultados

def extraer_importes(texto_completo):
    match_bloque = re.search(r"13\.\s*Valor de las ofertas:(.*?)(?=\s*14\.\s|\s*15\.\s|$)", texto_completo, re.IGNORECASE)
    if not match_bloque: return {}
    
    bloque13 = limpiar_basura_boe(match_bloque.group(1))
    trozos_lotes = dividir_por_lotes(bloque13, "13")
    
    resultados = {}
    for lote_nombre, chunk in trozos_lotes.items():
        sel = re.search(r"seleccionada:\s*([\d.,]+)", chunk)
        resultados[lote_nombre] = sel.group(1) if sel else "0,00"
    return resultados

# ══════════════════════════════════════════════════════════════════════════════
# PROCESAMIENTO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def filtrado_formalizaciones(fecha, datos):
    cpvs_objetivo = codigos_objetivo("codigosCPV.csv")
    if not cpvs_objetivo:
        return {"status": "error", "mensaje": "No se pudieron cargar los CPV objetivo."}

    tabla_A = []
    tabla_B = []

    for id_formalizacion, info in datos.items():
        cpvs_articulo = info.get("Códigos CPV", [])
        coincidencias = set(cpvs_articulo).intersection(cpvs_objetivo)
        if not coincidencias:
            continue

        print(f"  Coincidencia encontrada: {id_formalizacion}")

        url_pdf = info.get("PDF", "")
        if not url_pdf:
            print(f"  Sin PDF para {id_formalizacion}, omitiendo.")
            continue

        try:
            texto_limpio = descargar_y_extraer_texto(url_pdf)
        except Exception as e:
            print(f"  Error descargando PDF de {id_formalizacion}: {e}")
            continue

        metadatos = extraer_metadatos(texto_limpio)
        importes  = extraer_importes(texto_limpio)

        # Tabla A siempre que tengamos texto
        tabla_A.append({
            "ID Anuncio":      id_formalizacion,
            "Expediente":      metadatos.get("Expediente", ""),
            "Objeto":          metadatos.get("Objeto", ""),
            "PDF":             url_pdf,
            "CPV Coincidentes": ", ".join(coincidencias)
        })

        lotes_excluidos = []
        for lote, imp in importes.items():
            try:
                val = float(imp.replace(".", "").replace(",", "."))
                if val < 10000:
                    lotes_excluidos.append(lote)
            except ValueError:
                print(f"  Importe no parseable '{imp}' en lote '{lote}'")

        try:
            adjudicatarios_datos = extraer_adjudicatarios(texto_limpio, lotes_excluidos)
        except Exception as e:
            print(f"  Error extrayendo adjudicatarios de {id_formalizacion}: {e}")
            continue

        for lote_nombre, datos_adj in adjudicatarios_datos.items():
            tabla_B.append({
                "ID Anuncio":          id_formalizacion,
                "Num Lote":            lote_nombre,
                "Nombre Adjudicatario": datos_adj["Nombre Adjudicatario"],
                "NIF":                 datos_adj["NIF"],
                "Direccion":           datos_adj["Direccion"],
                "Localidad":           datos_adj["Localidad"],
                "Codigo Postal":       datos_adj["Codigo Postal"],
                "Pais":                datos_adj["Pais"],
                "PYME":                datos_adj["PYME"],
                "Importe":             importes.get(lote_nombre, "0,00")
            })

    columnas_A = ["ID Anuncio", "Expediente", "Objeto", "PDF", "CPV Coincidentes"]
    columnas_B = ["ID Anuncio", "Num Lote", "Nombre Adjudicatario", "NIF", "Direccion",
                  "Localidad", "Codigo Postal", "Pais", "PYME", "Importe"]

    exportar_a_csv(tabla_A, columnas_A, f"Anuncios_{fecha}")
    exportar_a_csv(tabla_B, columnas_B, f"Lotes_{fecha}")

    return {"status": "ok", "anuncios": len(tabla_A), "lotes": len(tabla_B)}