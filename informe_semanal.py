import json
import datetime
from pathlib import Path

def generar_informe_semana(fecha_referencia: datetime.date = None):
    """
    Agrega los adjudicatarios de lunes a viernes de la semana actual
    en un único JSON consolidado.
    """
    if fecha_referencia is None:
        fecha_referencia = datetime.date.today()

    # Calculamos el lunes y viernes de esa semana
    lunes = fecha_referencia - datetime.timedelta(days=fecha_referencia.weekday())
    dias_semana = [lunes + datetime.timedelta(days=i) for i in range(5)]  # Lun-Vie

    datos_semana = {}
    for dia in dias_semana:
        fecha_str = dia.strftime("%Y%m%d")
        ruta = Path("Adjudicaciones_Filtradas") / f"Adjudicatarios{fecha_str}.json"
        if ruta.exists():
            with open(ruta, "r", encoding="utf-8") as f:
                datos_dia = json.load(f)
            datos_semana.update(datos_dia)
            print(f"  Añadido: {fecha_str} ({len(datos_dia)} registros)")
        else:
            print(f"  Sin datos: {fecha_str}")

    if not datos_semana:
        print("No hay datos para esta semana.")
        return

    semana_str = lunes.strftime("%Y%m%d")
    ruta_salida = Path("Adjudicaciones_Filtradas") / f"Semana_{semana_str}.json"
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos_semana, f, indent=4, ensure_ascii=False)
    print(f"Informe semanal guardado en: {ruta_salida}")
    return datos_semana