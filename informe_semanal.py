import csv
import datetime
from pathlib import Path

COLUMNAS_A = ["ID Anuncio", "Expediente", "Objeto", "PDF", "CPV Coincidentes"]
COLUMNAS_B = ["ID Anuncio", "Num Lote", "Nombre Adjudicatario", "NIF", "Direccion",
              "Localidad", "Codigo Postal", "Pais", "PYME", "Importe"]

def leer_csv(ruta: Path) -> list[dict]:
    with open(ruta, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def escribir_csv(ruta: Path, filas: list[dict], columnas: list[str]):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)

def generar_informe_semana(fecha_referencia: datetime.date = None):
    """
    Agrega los CSV de anuncios y lotes de lunes a viernes de la semana
    en dos CSV consolidados con fecha del lunes.
    """
    if fecha_referencia is None:
        fecha_referencia = datetime.date.today()

    lunes = fecha_referencia - datetime.timedelta(days=fecha_referencia.weekday())
    dias_semana = [lunes + datetime.timedelta(days=i) for i in range(5)]  # Lun-Vie
    semana_str = lunes.strftime("%Y%m%d")

    directorio = Path("Adjudicaciones_Filtradas")
    filas_anuncios = []
    filas_lotes    = []

    for dia in dias_semana:
        fecha_str = dia.strftime("%Y%m%d")
        ruta_a = directorio / f"Anuncios_{fecha_str}.csv"
        ruta_b = directorio / f"Lotes_{fecha_str}.csv"

        if not ruta_a.exists() and not ruta_b.exists():
            print(f"  Sin datos: {fecha_str}")
            continue

        if ruta_a.exists():
            filas_dia = leer_csv(ruta_a)
            filas_anuncios.extend(filas_dia)
            print(f"  Anuncios {fecha_str}: {len(filas_dia)} registros")

        if ruta_b.exists():
            filas_dia = leer_csv(ruta_b)
            filas_lotes.extend(filas_dia)
            print(f"  Lotes    {fecha_str}: {len(filas_dia)} registros")

    if not filas_anuncios and not filas_lotes:
        print("No hay datos para esta semana.")
        return

    ruta_informe_a = directorio / f"Informe_Anuncios_{semana_str}.csv"
    ruta_informe_b = directorio / f"Informe_Lotes_{semana_str}.csv"

    escribir_csv(ruta_informe_a, filas_anuncios, COLUMNAS_A)
    escribir_csv(ruta_informe_b, filas_lotes,    COLUMNAS_B)

    print(f"\nInforme semanal generado:")
    print(f"  Anuncios : {ruta_informe_a} ({len(filas_anuncios)} filas)")
    print(f"  Lotes    : {ruta_informe_b} ({len(filas_lotes)} filas)")

    return {"anuncios": filas_anuncios, "lotes": filas_lotes}