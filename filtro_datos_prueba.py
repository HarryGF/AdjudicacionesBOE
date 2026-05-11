import io
import json
import csv
import os
import re
import requests
import pdfplumber

# --- CONFIGURACIÓN Y PATRONES ---
# Agrupamos los patrones para que sea fácil modificarlos en un solo sitio
PATRONES_METADATOS = {
    "Objeto": r"(?i)Objeto:\s*(.*?)(?=Expediente:|$)",
    "Expediente": r"(?i)Expediente:\s*(.*?)(?=\s*\d+\.\s+[A-Z]|$)"
}

# --- FUNCIONES DE APOYO ---

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

def cargar_cpvs_objetivo(ruta_csv):
    cpvs = set()
    try:
        if not os.path.exists(ruta_csv):
            return cpvs
        with open(ruta_csv, "r", encoding="utf-8") as f:
            lector = csv.reader(f)
            next(lector, None)
            for fila in lector:
                if not fila: continue
                codigo = fila[0].split('-')[0].strip()
                if len(codigo) == 8 and codigo.isdigit():
                    cpvs.add(codigo)
        print(f"Cargados {len(cpvs)} códigos CPV.")
        return cpvs
    except Exception as e:
        print(f"Error cargando CSV: {e}")
        return set()

def descargar_y_extraer_texto(url_pdf):
    """Descarga el PDF y devuelve el texto normalizado en una sola línea."""
    res = requests.get(url_pdf, timeout=15)
    res.raise_for_status()
    with pdfplumber.open(io.BytesIO(res.content)) as pdf:
        texto = " ".join((p.extract_text() or "") for p in pdf.pages)
        return re.sub(r'\s+', ' ', texto)

def limpiar_basura_boe(texto):
    patron_basura = r"BOLETÍN OFICIAL DEL ESTADO.*?elbacifireV\s*"
    return re.sub(patron_basura, "", texto)

# --- FUNCIONES DE EXTRACCIÓN (REGEX) ---

def extraer_metadatos(texto):
    res = {}
    for campo, patron in PATRONES_METADATOS.items():
        match = re.search(patron, texto)
        res[campo] = match.group(1).strip() if match else ""
    return res

def extraer_importes(texto_completo):
    # Extraemos solo el bloque 13 (se detiene en el 14, 15 o final)
    match_bloque = re.search(r"13\.\s*Valor de las ofertas:(.*?)(?=\s*14\.\s|\s*15\.\s|$)", texto_completo, re.IGNORECASE)
    if not match_bloque: return {}
    
    bloque13 = limpiar_basura_boe(match_bloque.group(1))
    trozos_lotes = dividir_por_lotes(bloque13, "13")
    
    resultados = {}
    for lote_nombre, chunk in trozos_lotes.items():
        sel = re.search(r"seleccionada:\s*([\d.,]+)", chunk)
        may = re.search(r"mayor coste:\s*([\d.,]+)", chunk)
        men = re.search(r"menor coste:\s*([\d.,]+)", chunk)
        
        resultados[lote_nombre] = {
            "Valor Oferta Seleccionada": sel.group(1) if sel else "0,00",
            "Valor Oferta Mayor": may.group(1) if may else "0,00",
            "Valor Oferta Menor": men.group(1) if men else "0,00"
        }
    return resultados

def parsear_adjudicatarios(texto_completo):
    # Extraemos solo el bloque 12
    patron_bloque = r"12\.\s*Adjudicatarios:(.*?)(?=13\.\s+Valor|$)"
    match_bloque = re.search(patron_bloque, texto_completo)
    if not match_bloque: return {}

    bloque12 = limpiar_basura_boe(match_bloque.group(1))
    trozos_lotes = dividir_por_lotes(bloque12, "12")
    
    # Condición de parada para leer campos independientemente de si es 12.1) o 12.1.2)
    sig_campo = r"(?=\s*\d+\.(?:\d+\.)*\d+\)|$)" 
    
    resultados = {}
    for lote_nombre, chunk in trozos_lotes.items():
        m_nom = re.search(r"12\.\sNombre:\s*(.*?)\." + sig_campo, chunk)
        m_nif = re.search(r"Número de identificación fiscal:\s*([A-Z0-9]+)", chunk)
        m_dir = re.search(r"Dirección:\s*(.*?)\." + sig_campo, chunk)
        m_loc = re.search(r"Localidad:\s*(.*?)\." + sig_campo, chunk)
        m_cp = re.search(r"Código postal:\s*(\d+)", chunk)
        m_pais = re.search(r"País:\s*(.*?)\." + sig_campo, chunk)
        
        datos = {
            "Nombre Adjudicatario": m_nom.group(1).strip() if m_nom else "",
            "NIF": m_nif.group(1).strip() if m_nif else "SIN_NIF",
            "Direccion": m_dir.group(1).strip() if m_dir else "No disponible",
            "Localidad": m_loc.group(1).strip() if m_loc else "",
            "Codigo Postal": m_cp.group(1).strip() if m_cp else "",
            "Pais": m_pais.group(1).strip() if m_pais else ""
        }
        
        datos["PYME"] = "si" if "es una pyme" in chunk.lower() and "no es" not in chunk.lower() else "no"
        
        nif = datos.pop("NIF")
        resultados[lote_nombre] = {nif: datos}
        
    return resultados

def exportar_json(datos, prefijo, fecha):
    os.makedirs("Adjudicaciones_Filtradas", exist_ok=True)
    ruta = f"Adjudicaciones_Filtradas/{prefijo}{fecha}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)
    print(f"Exportado: {ruta}")

# --- PIPELINE PRINCIPAL ---

def ejecutar_pipeline(fecha_proceso):
    cpvs_objetivo = cargar_cpvs_objetivo("Codigos_CPV_IESMAT.csv")
    ruta_input = f"Datos_Procesados/{fecha_proceso}.json"
    
    if not os.path.exists(ruta_input):
        print(f"No se encuentra el archivo de entrada para {fecha_proceso}")
        return

    with open(ruta_input, "r", encoding="utf-8") as f:
        datos_licitaciones = json.load(f)

    formalizaciones_finales = {}
    adjudicatarios_finales = {}

    for id_lic, info in datos_licitaciones.items():
        # Filtrado por CPV
        coincidencias = set(info.get("Códigos CPV", [])).intersection(cpvs_objetivo)
        if not coincidencias:
            continue

        print(f" Procesando {id_lic}...")
        
        try:
            texto_pdf = descargar_y_extraer_texto(info["PDF"])
            
            # Extraer Datos
            metadatos = extraer_metadatos(texto_pdf)
            importes = extraer_importes(texto_pdf)
            adjudicatarios_data = parsear_adjudicatarios(texto_pdf)

            # Construir objeto de formalización
            item = dict(info)
            item["CPV Coincidentes"] = list(coincidencias)
            item.update(metadatos)
            
            # Guardamos los importes (vendrán agrupados por Lote o como 'General')
            if importes:
                item["Importes"] = importes
            
            formalizaciones_finales[id_lic] = item
            
            # Guardamos los adjudicatarios
            if adjudicatarios_data:
                adjudicatarios_finales[id_lic] = adjudicatarios_data
            
            print(f"   [OK] Lotes detectados: {', '.join(importes.keys()) if importes else 'Ninguno'}")

        except Exception as e:
            print(f"   [Error] {id_lic}: {e}")

    print(formalizaciones_finales)
    print(adjudicatarios_finales)
    # Guardar Resultados
    #if formalizaciones_finales:
    #    exportar_json(formalizaciones_finales, "Documento", fecha_proceso)
    #    exportar_json(adjudicatarios_finales, "Adjudicatarios", fecha_proceso)
    #else:
    #    print("No se encontraron coincidencias finales para exportar.")
1
if __name__ == "__main__":
    ejecutar_pipeline("20260428")