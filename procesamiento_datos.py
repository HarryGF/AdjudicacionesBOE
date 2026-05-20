import json
import os
from weakref import ref

import ollama

MODELO = "qwen2.5:3b"

SYSTEM_PROMPT = """Eres un extractor de datos estricto para contratación pública. Tu única tarea es encontrar todos los códigos CPV (números exactos de 8 dígitos) en el texto.

REGLAS CRÍTICAS:
1. NO OMITAS NINGÚN CÓDIGO. Si hay 22 códigos en el texto, debes devolver los 22.
2. NO resumas ni agrupes.
3. NO inventes ni deduzcas códigos por el contexto. Extrae solo lo que está escrito explícitamente.

Devuelve ÚNICAMENTE un objeto JSON con los códigos encontrados.

Ejemplo de entrada: 
Texto: Servicio externo de prevención de riesgos laborales... (CPV: 85120000 y 85147000).

Ejemplo de salida exacta: 
{"cpv": ["85120000", "85147000"]}
"""


def ejecutar_procesamiento(fecha_str, datos):
    """
    Procesa los datos brutos de las licitaciones utilizando un modelo de IA local (Ollama)
    para extraer de forma precisa los códigos CPV.

    Args:
        fecha_str (str): Cadena de texto con la fecha en formato 'YYYYMMDD' que 
                         identifica el archivo de entrada en 'Datos_Brutos'.

    Returns:
        dict: Un diccionario con el estado del proceso ('status') y, en caso de éxito, 
              la 'cantidad' de licitaciones procesadas. Si no encuentra el archivo,
              devuelve un diccionario con el estado 'error' y su mensaje correspondiente.
    """
    ruta_salida = f"Datos_Procesados/{fecha_str}.json"  
    os.makedirs("Datos_Procesados", exist_ok=True)
    datos_filtrados = {}

    for id_licitacion, info in datos.items():
        descripcion = info.get('descripcion_bruta', '').strip()
        cpv_bruto = info.get('cpv_bruto', [])

        # 1. OPTIMIZACIÓN: Cláusula de guarda para evitar llamadas innecesarias a la IA
        if not descripcion or descripcion.lower() == "no encontrada":
            datos_filtrados[id_licitacion] = {
                "Códigos CPV": cpv_bruto, # Mantenemos lo que ya venía de la API
                "PDF": info.get('pdf', ''),
                "nota": "Procesado sin IA (sin descripción válida)"
            }
            continue # Saltamos a la siguiente licitación sin tocar Ollama

        prompt_usuario = f"""
        Extrae los códigos CPV de la siguiente licitación. 
        Códigos CPV actuales: {cpv_bruto}
        Descripción licitación: {descripcion}
        """

        try:
            # Llamada al modelo local mediante Ollama
            response = ollama.chat(
                model=MODELO,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt_usuario}
                ],
                format='json',
                keep_alive='1m', # 2. OPTIMIZACIÓN: Descarga el modelo de la RAM 1 min después de acabar el script
                options={
                    'temperature': 0.0,   
                    'num_predict': 256,   
                    'num_ctx': 1024,     # 3. OPTIMIZACIÓN: Reduce el uso de RAM limitando el contexto
                    'top_p': 0.1           
                }
            )
            
            respuesta_texto = response['message']['content']
            datos_extraidos = json.loads(respuesta_texto)
            lista_cpv = datos_extraidos.get("cpv", [])
            
            datos_filtrados[id_licitacion] = {
                "Códigos CPV": lista_cpv,
                "PDF": info.get('pdf', '')
            }
            
        except Exception as e:
            datos_filtrados[id_licitacion] = info
            datos_filtrados[id_licitacion]["error_ia"] = str(e)

    # Exportamos los datos procesados
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos_filtrados, f, indent=4, ensure_ascii=False)

    return {"status": "ok", "cantidad": len(datos_filtrados), "datos": datos_filtrados}