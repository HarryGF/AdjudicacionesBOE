import datetime
import json
import os 
from pathlib import Path
from dotenv import load_dotenv
from email.message import EmailMessage
import ssl
import smtplib

import lock
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
        if not lock.adquirir_lock("scheduler"):
            print("ERROR: Pipeline ya en ejecución. ")
            exit(1)
        try:
            resultado = ejecutar_dia(fecha_str)

            if hoy.weekday() == 4:  # Viernes: informe semanal + correo
                datos_semana = informe_semanal.generar_informe_semana(hoy)

                lunes = hoy - datetime.timedelta(days=hoy.weekday())
                lunes_str = lunes.strftime("%Y%m%d")
                ruta_anuncios = Path("Adjudicaciones_Filtradas") / f"Informe_Anuncios_{lunes_str}.csv"
                ruta_lotes    = Path("Adjudicaciones_Filtradas") / f"Informe_Lotes_{lunes_str}.csv"

                n_anuncios = len(datos_semana.get("anuncios", [])) if datos_semana else 0
                n_lotes    = len(datos_semana.get("lotes",    [])) if datos_semana else 0

                load_dotenv()
                em = EmailMessage()
                em["From"]    = os.getenv("SENDER")
                em["To"]      = os.getenv("RECEIVER")
                em["Subject"] = f"Informe Semanal BOE (Adjudicaciones) — Semana del {lunes.strftime('%d/%m/%Y')}"
                em.set_content(
                    f"Informe semanal correspondiente a la semana del {lunes.strftime('%d/%m/%Y')}.\n\n"
                    f"Anuncios : {n_anuncios}\n"
                    f"Lotes    : {n_lotes}\n"
                )

                for ruta_csv in (ruta_anuncios, ruta_lotes):
                    if ruta_csv.exists():
                        with open(ruta_csv, "rb") as f:
                            em.add_attachment(
                                f.read(),
                                maintype="text",
                                subtype="csv",
                                filename=ruta_csv.name
                            )

                context = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                    smtp.login(em["From"], os.getenv("CONTRASEÑA"))
                    smtp.sendmail(em["From"], em["To"], em.as_string())

                print(f"Correo enviado a {em['To']}")

        finally:
            lock.liberar_lock()

    resultado["fecha"]     = fecha_str
    resultado["timestamp"] = datetime.datetime.now().isoformat()
    resultado.pop("datos", None)

    with open(ruta_log, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=4, ensure_ascii=False)