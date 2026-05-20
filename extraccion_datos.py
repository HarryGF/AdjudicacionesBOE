import io
import json
import os
import re
import time

import pdfplumber
import requests

HEADERS = {"Accept": "application/json"}
BASE_URL = "https://boe.es/datosabiertos/api/boe/sumario/"


def asegurar_lista(elemento):
    """
    Garantiza que el elemento proporcionado siempre se devuelva como una lista.

    Args:
        elemento (any): El elemento que se desea verificar o convertir.

    Returns:
        list: Una lista vacía si el elemento es None, el mismo elemento si ya 
              es una lista, o el elemento envuelto en una lista si es de otro tipo.
    """
    if elemento is None:
        return []
    if isinstance(elemento, list):
        return elemento
    return [elemento]


def buscar_formalizaciones(datos):
    """
    Recorre el sumario en formato JSON del BOE para encontrar anuncios de licitación.

    Args:
        datos (dict): Diccionario con los datos parseados de la API del BOE.

    Returns:
        list: Una lista de diccionarios, donde cada diccionario contiene la 
              información básica de una licitación ('id', 'titulo', 'pdf').
    """
    formalizaciones = []
    palabras_clave = ["adjudicación", "adjudicacion", "formalización", "formalizacion"]
    diarios = asegurar_lista(datos.get("data", {}).get("sumario", {}).get("diario", []))

    for diario in diarios:
        secciones = asegurar_lista(diario.get("seccion", []))
        for seccion in secciones:
            # Filtramos por la sección 5 o aquellas que contengan "Anuncios"
            if seccion.get("codigo") == "5" or "Anuncios" in seccion.get("nombre", ""):
                deptos = asegurar_lista(seccion.get("departamento", []))
                for depto in deptos:
                    items = []
                    epigrafes = asegurar_lista(depto.get("epigrafe", []))
                    for epi in epigrafes:
                        items.extend(asegurar_lista(epi.get("item", [])))
                    items.extend(asegurar_lista(depto.get("item", [])))

                    for item in items:
                        titulo = item.get("titulo", "")
                        # Comprobamos si alguna palabra clave está en el título
                        if any(p in titulo.lower() for p in palabras_clave):
                            formalizaciones.append({
                                "id": item.get("identificador"),
                                "titulo": titulo,
                                "pdf": item.get("url_pdf", {}).get("texto")
                            })
    return formalizaciones


def extraer_datos_pdf(url_pdf):
    """
    Descarga un PDF desde una URL y extrae información específica mediante expresiones regulares.

    Args:
        url_pdf (str): La URL directa al documento PDF.

    Returns:
        dict: Un diccionario con los datos extraídos ('perfil_comprador', 'cpv', 
              'descripcion', 'pliegos_contratacion') o un mensaje de 'error'.
    """
    try:
        response = requests.get(url_pdf, timeout=10)
        if response.status_code != 200:
            return {"error": f"Error HTTP {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    try:
        # Abrimos el PDF en memoria sin necesidad de guardarlo en disco
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            texto_completo = ""
            for page in pdf.pages:
                texto = page.extract_text(layout=True)
                if texto:
                    texto_completo += texto + "\n"

        texto_limpio = re.sub(r'\s+', ' ', texto_completo)

        patron_cpv = r"(?i)Códigos CPV:\s*(.*?)(?=\s*\d+\.\s+[A-Z])"
        patron_descripcion = r"(?i)Descripción de la licitación:\s*(.*?)(?=\s*\d+\.\s+[A-Z]|$)"

        descripcion = re.search(patron_descripcion, texto_limpio)
        match_cpv = re.search(patron_cpv, texto_limpio)
        
        lista_cpvs = []
        if match_cpv:
            bloque_texto_cpv = match_cpv.group(1)
            todos_los_cpv = re.findall(r'\b\d{8}\b', bloque_texto_cpv)
            lista_cpvs = list(set(todos_los_cpv))

        return {
            "cpv": lista_cpvs,
            "descripcion": descripcion.group(1).strip() if descripcion else "No encontrada"
        }
        
    except Exception as e:
        return {"error": f"Error procesando PDF: {str(e)}"}


def ejecutar_extraccion(fecha_str):
    """
    Función principal (pipeline) que orquesta la extracción de datos de un día específico.

    Args:
        fecha_str (str): Cadena de texto con la fecha en formato 'YYYYMMDD'.

    Returns:
        dict: Un diccionario con el estado del proceso ('status') y la 'cantidad' 
              de licitaciones procesadas con éxito.
    """
    url = f"{BASE_URL}{fecha_str}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return {"status": "error", "mensaje": f"Error {response.status_code}: {response.text}"}

    data = response.json()
    lista_formalizaciones = buscar_formalizaciones(data)

    if not lista_formalizaciones:
        return {"status": "ok", "cantidad": 0, "mensaje": "No hay licitaciones hoy."}
        
    print(f"\nEncontradas {len(lista_formalizaciones)} posibles formalizaciones. Iniciando descarga de PDFs...")

    formalizaciones_completas = []
    
    for formalizacion in lista_formalizaciones:
        url_pdf = formalizacion['pdf']
        if url_pdf:
            datos_extraidos = extraer_datos_pdf(url_pdf)
            formalizacion_fusionada = {**formalizacion, **datos_extraidos}
            formalizaciones_completas.append(formalizacion_fusionada)
            time.sleep(0.5) 

    os.makedirs("Datos_Brutos", exist_ok=True)

    datos_brutos = {}
    
    for res in formalizaciones_completas:
        datos_brutos[res['id']] = {
            "titulo": res['titulo'],
            "cpv_bruto": res.get('cpv', []), 
            "descripcion_bruta": res.get('descripcion', ''),
            "pdf": res['pdf']
        }
        
    # Guardamos los resultados en formato JSON
    ruta_salida = f"Datos_Brutos/{fecha_str}.json"
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos_brutos, f, indent=4, ensure_ascii=False)
        
    return {"status": "ok", "cantidad": len(formalizaciones_completas), "datos": datos_brutos}