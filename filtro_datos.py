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
        # Cortamos hasta el inicio del siguiente lote, o hasta el final del texto
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

def exportar_datos(datos, nombre, fecha):
    os.makedirs("Adjudicaciones_Filtradas", exist_ok=True)
    ruta = f"Adjudicaciones_Filtradas/{nombre}{fecha}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)
    print(f"Resultados exportados a: {ruta}")

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
    
    # Condición de parada para leer campos independientemente de si es 12.1) o 12.1.2)
    sig_campo = r"(?=\s*\d+\.(?:\d+\.)*\d+\)|$)" 
    lista_nif = []
    resultados = {}

    for lote_nombre, chunk in trozos_lotes.items():
        if lote_nombre in lista_lotes:
            continue

        m_nom = re.search(r"12\.[0-9]*\.*[0-9]*\)\sNombre:\s*(.*?)\." + sig_campo, chunk)
        m_nif = re.search(r"Número de identificación fiscal:\s*([A-Z0-9]+)", chunk)
        m_dir = re.search(r"Dirección:\s*(.*?)\." + sig_campo, chunk)
        m_loc = re.search(r"Localidad:\s*(.*?)\." + sig_campo, chunk)
        m_cp = re.search(r"Código postal:\s*(\d+)", chunk)
        m_pais = re.search(r"País:\s*(.*?)\." + sig_campo, chunk)
        
        nif = m_nif.group(1).strip() if m_nif else "SIN_NIF"

        datos = {
            "Nombre Adjudicatario": m_nom.group(1).strip() if m_nom else "",
            "NIF": m_nif.group(1).strip() if m_nif else "SIN_NIF",
            "Direccion": m_dir.group(1).strip() if m_dir else "No disponible",
            "Localidad": m_loc.group(1).strip() if m_loc else "",
            "Codigo Postal": m_cp.group(1).strip() if m_cp else "",
            "Pais": m_pais.group(1).strip() if m_pais else ""
        }
        
        datos["PYME"] = "si" if "es una pyme" in chunk.lower() and "no es" not in chunk.lower() else "no"
        resultados[lote_nombre] = datos
        lista_nif.append(nif)

    return resultados, lista_nif

def extraer_importes(texto_completo):
    # Extraemos solo el bloque 13 (se detiene en el 14, 15 o final)
    match_bloque = re.search(r"13\.\s*Valor de las ofertas:(.*?)(?=\s*14\.\s|\s*15\.\s|$)", texto_completo, re.IGNORECASE)
    if not match_bloque: return {}
    
    bloque13 = limpiar_basura_boe(match_bloque.group(1))
    trozos_lotes = dividir_por_lotes(bloque13, "13")
    
    resultados = {}
    for lote_nombre, chunk in trozos_lotes.items():
        sel = re.search(r"seleccionada:\s*([\d.,]+)", chunk)
        
        resultados[lote_nombre] = sel.group(1) if sel else "0,00"
    return resultados

def filtrado_formalizaciones(fecha, datos):
    csv_objetivo = "Codigos_CPV_IESMAT.csv"
    cpvs_objetivo = codigos_objetivo(csv_objetivo)
    if not cpvs_objetivo:
        return {"status": "error", "mensaje": "No se pudieron cargar los CPV objetivo."}

    formalizaciones_encontradas = {}
    adjudicatarios = {}

    for id_formalizacion, info in datos.items():
        cpvs_articulo = info.get("Códigos CPV", [])
        if not cpvs_articulo:
            continue

        coincidencias = set(cpvs_articulo).intersection(cpvs_objetivo)
        if not coincidencias:
            continue

        print(f"  Coincidencia encontrada: {id_formalizacion}")
        formalizacion = dict(info)

        url_pdf = info["PDF"]
        if not url_pdf:
            formalizacion["Adjudicatarios"] = []
            formalizaciones_encontradas[id_formalizacion] = formalizacion
            continue
        texto_limpio = descargar_y_extraer_texto(info["PDF"])

        metadatos = extraer_metadatos(texto_limpio)
        importes = extraer_importes(texto_limpio)
        lista_lotes = []
        for lote_nombre, importe in importes.items():
            x = importe.replace(".","")
            y = x.replace(",",".")
            if float(y) < 10000:
                lista_lotes.append(lote_nombre)
        try:
            adjudicatarios_datos, lista_nif = extraer_adjudicatarios(texto_limpio, lista_lotes) 

            if adjudicatarios_datos:
                adjudicatarios[id_formalizacion] = adjudicatarios_datos
                if importes:
                    for lote_nombre, importe in importes.items():
                        for nif in lista_nif:
                            adjudicatarios[id_formalizacion][lote_nombre]["Importe"] = importe
            
                    item = dict(info)
                    item["CPV Coincidentes"] = list(coincidencias)
                    item.update(metadatos)
                    
                    formalizaciones_encontradas[id_formalizacion] = item
        except Exception as e:
            return {"status": "error", "mensaje": f"{id_formalizacion}: {e}"}

    print(f"\nTotal formalizaciones coincidentes: {len(formalizaciones_encontradas)}")
    if not formalizaciones_encontradas:
        return {"status": "ok", "cantidad": 0, "mensaje": "No hay formalizaciones coincidentes."}

    exportar_datos(formalizaciones_encontradas, "Documento",fecha)
    exportar_datos(adjudicatarios, "Adjudicatarios",fecha)
    return {"status": "ok", "cantidad": len(formalizaciones_encontradas), "datos": adjudicatarios}