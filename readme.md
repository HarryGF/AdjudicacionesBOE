# BOE Adjudicaciones

Pipeline automatizado de extracción, procesamiento y filtrado de contratos adjudicados publicados en el Boletín Oficial del Estado (BOE), con interfaz visual en Streamlit e informe semanal por correo electrónico.

---

## ¿Qué hace este proyecto?

Cada día laborable el sistema:

1. Consulta la API del BOE y descarga los anuncios de formalización de contratos.
2. Usa un modelo de IA local (Ollama) para normalizar y extraer con precisión los códigos CPV de cada anuncio.
3. Filtra los contratos que coincidan con los CPV de interés definidos por el usuario.
4. Descarga el PDF de cada contrato coincidente y extrae los datos del adjudicatario (empresa, NIF, importe, etc.).
5. Exporta los resultados en dos archivos CSV: uno de anuncios y otro de lotes.
6. Los viernes, consolida los datos de toda la semana en un informe CSV y lo envía por correo electrónico.

---

## Estructura del proyecto

```
BOE_Adjudicaciones/
│
├── extraccion_datos.py       # Paso 1 – Consulta la API del BOE y extrae datos básicos de los PDFs
├── procesamiento_datos.py    # Paso 2 – Normaliza los CPV con IA local (Ollama / qwen2.5:3b)
├── filtro_datos.py           # Paso 3 – Filtra por CPV objetivo y extrae adjudicatarios
├── informe_semanal.py        # Agrega los CSV diarios en un informe semanal
├── ejecutar_pipeline.py      # Orquestador principal: ejecuta la pipeline y envía el correo
├── consola.py                # Interfaz visual con Streamlit
├── ejecutar_codigo.bat       # Lanzador para Windows (arranca Ollama y ejecuta la pipeline)
│
├── codigosCPV.csv            # Lista de códigos CPV de interés (entrada del usuario)
├── .env                      # Credenciales de correo (no subir a Git)
│
├── Datos_Brutos/          # JSONs con datos crudos extraídos del BOE
├── Datos_Procesados/      # JSONs con CPVs normalizados por la IA
├── Adjudicaciones_Filtradas/  # CSVs de resultados diarios e informes semanales
└── Logs_Pipeline/         # JSONs de log por cada ejecución
```

---

## Flujo de datos

```
API BOE → extraccion_datos.py → Datos_Brutos/{fecha}.json
                                        ↓
                          procesamiento_datos.py (Ollama)
                                        ↓
                              Datos_Procesados/{fecha}.json
                                        ↓
                              filtro_datos.py + codigosCPV.csv
                                        ↓
                   Anuncios_{fecha}.csv + Lotes_{fecha}.csv
                                        ↓ (viernes)
                   Informe_Anuncios_{lunes}.csv + Informe_Lotes_{lunes}.csv
                                        ↓
                                  Correo electrónico
```

---

## Archivos de salida

### Diarios
| Archivo | Contenido |
|---|---|
| `Anuncios_{fecha}.csv` | Un registro por contrato: expediente, objeto, CPVs coincidentes, enlace al PDF |
| `Lotes_{fecha}.csv` | Un registro por adjudicatario/lote: empresa, NIF, dirección, importe, PYME |

### Semanales (generados los viernes)
| Archivo | Contenido |
|---|---|
| `Informe_Anuncios_{lunes}.csv` | Consolidado de `Anuncios_*.csv` de lunes a viernes |
| `Informe_Lotes_{lunes}.csv` | Consolidado de `Lotes_*.csv` de lunes a viernes |

---

## Requisitos

- Python 3.10+
- [Ollama](https://ollama.com/) instalado y corriendo con el modelo `qwen2.5:3b`(este modelo se puede modificar según las especificacioens de tu ordenador)
- Cuenta de Gmail con [contraseña de aplicación](https://myaccount.google.com/apppasswords) generada

### Instalación de dependencias

```bash
pip install -r requirements.txt
```

### Descargar el modelo de IA

```bash
ollama pull qwen2.5:3b
```

---

## Configuración

### 1. Códigos CPV de interés — `codigosCPV.csv`

Crea un archivo `codigosCPV.csv` en la raíz del proyecto con los códigos CPV que quieres monitorizar. El formato esperado es un código por fila, opcionalmente con descripción separada por guion:

```
CPV
30216100-1
38000000-5
72000000-5
```

### 2. Credenciales de correo — `.env`

Crea un archivo `.env` en la raíz del proyecto:

```env
SENDER=tu_correo@gmail.com
RECEIVER=destino@empresa.com
CONTRASEÑA=xxxx xxxx xxxx xxxx
```

> La contraseña debe ser una **contraseña de aplicación** de Google, no tu contraseña habitual.

---

## Ejecución

### Ejecución manual (Windows)

Haz doble clic en `ejecutar_codigo.bat`. El script:
- Comprueba si Ollama está corriendo y lo arranca si no.
- Ejecuta `ejecutar_pipeline.py`.
- Guarda la salida en `Logs_Pipeline/output.txt`.

### Ejecución manual (terminal)

```bash
python ejecutar_pipeline.py
```

### Automatización diaria

Para ejecutar la pipeline automáticamente cada día laborable se recomienda usar el **Programador de tareas de Windows** apuntando a `ejecutar_codigo.bat`, o `cron` en Linux/macOS:

```bash
# Ejemplo cron: ejecutar de lunes a sábado a las 9:00
0 9 * * 1-6 /usr/bin/python3 /ruta/proyecto/ejecutar_pipeline.py
```

El propio script omite la ejecución los domingos (el BOE no publica ese día).

### Interfaz visual (Streamlit)

```bash
streamlit run consola.py
```

La consola permite:
- Ejecutar la pipeline para cualquier fecha.
- Ver los resultados agrupados por formalización y lote.
- Explorar cualquier CSV generado.
- Generar y visualizar el informe semanal.

---

## Lógica de filtrado

- Solo se procesan los contratos cuyo CPV coincide con alguno de los definidos en `codigosCPV.csv`.
- Los lotes con importe inferior a **10.000 €** se excluyen automáticamente del CSV de lotes(este filtro se puede modificar en linea 197 del código filtro_datos).
- Si el PDF de un contrato no está disponible o falla la descarga, el anuncio se omite sin interrumpir el proceso.

---

## Logs

Cada ejecución genera un archivo `Logs_Pipeline/{fecha}.json` con el estado del proceso:

```json
{
    "status": "ok",
    "anuncios": 3,
    "lotes": 5,
    "fecha": "20260513",
    "timestamp": "2026-05-13T09:01:22.345678"
}
```

Los posibles valores de `status` son `ok`, `error` y `omitido` (domingos).

---

## Notas

- El modelo de IA se usa exclusivamente para mejorar la extracción de CPVs; si Ollama no está disponible, el sistema preserva los CPVs extraídos directamente del PDF sin interrumpir la pipeline.
- Los archivos en `Datos_Brutos/`, `Datos_Procesados/` y `Adjudicaciones_Filtradas/` se acumulan por fecha y no se sobreescriben en ejecuciones normales.
- Se recomienda añadir `.env` y las carpetas de datos al `.gitignore`.

---