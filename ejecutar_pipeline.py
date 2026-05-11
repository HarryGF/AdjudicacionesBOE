# ejecutar_pipeline.py
import datetime
import json
from pathlib import Path

import extraccion_datos
import procesamiento_datos
import filtro_datos
import informe_semanal

LOG_DIR = Path("Logs_Pipeline")

def ejecutar_dia(fecha_str: str) -> dict:
    r1 = extraccion_datos.ejecutar_extraccion(fecha_str)
    if r1["status"] == "error" or r1.get("cantidad", 0) == 0:
        return r1

    r2 = procesamiento_datos.ejecutar_procesamiento(fecha_str, r1["datos"])
    if r2["status"] == "error":
        return r2

    r3 = filtro_datos.filtrado_formalizaciones(fecha_str, r2["datos"])
    return r3

if __name__ == "__main__":
    hoy = datetime.date.today()
    fecha_str = hoy.strftime("%Y%m%d")
    
    LOG_DIR.mkdir(exist_ok=True)
    ruta_log = LOG_DIR / f"{fecha_str}.json"

    if hoy.weekday() == 6:
        resultado = {"status": "omitido", "mensaje": "Domingo: sin publicación en el BOE."}
    else:
        resultado = ejecutar_dia(fecha_str)

        if hoy.weekday() == 4:  # Viernes
            informe_semanal.generar_informe_semana(hoy)

    resultado["fecha"] = fecha_str
    resultado["timestamp"] = datetime.datetime.now().isoformat()

    # Eliminamos "datos" del log para no duplicar lo que ya guardan los otros módulos
    resultado.pop("datos", None)

    with open(ruta_log, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=4, ensure_ascii=False)