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
        prompt_usuario = f"""
        Extrae los códigos CPV de la siguiente licitación. 
        Códigos CPV actuales: {info.get('cpv_bruto', '')}
        Descripción licitación: {info.get('descripcion_bruta', '')}
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
                options={
                    'temperature': 0.0,    # Creatividad cero para máxima precisión
                    'num_predict': 256,    # Limitamos la respuesta para ahorrar VRAM
                    'top_p': 0.1           # Enfocamos al modelo en las respuestas más probables
                }
            )
            
            respuesta_texto = response['message']['content']
            datos_extraidos = json.loads(respuesta_texto)
            lista_cpv = datos_extraidos.get("cpv", [])
            
            # Guardamos solo los datos relevantes para la siguiente fase
            datos_filtrados[id_licitacion] = {
                "Códigos CPV": lista_cpv,
                "PDF": info.get('pdf', '')
            }
            
        except Exception as e:
            # Si la IA falla (ej. timeout, modelo no encendido, JSON mal formado), 
            # preservamos la información original para no perder el registro.
            datos_filtrados[id_licitacion] = info
            datos_filtrados[id_licitacion]["error_ia"] = str(e)

    # Exportamos los datos procesados a la nueva carpeta
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos_filtrados, f, indent=4, ensure_ascii=False)

    return {"status": "ok", "cantidad": len(datos_filtrados), "datos":datos_filtrados}