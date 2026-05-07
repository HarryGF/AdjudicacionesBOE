# BOE Formalizaciones

Pipeline automatizado de extracción, procesamiento y filtrado de contratos adjudicados publicados en el **Boletín Oficial del Estado (BOE)**, con interfaz web construida en Streamlit.

---

## Descripción

Este proyecto conecta con la API abierta del BOE para identificar anuncios de formalización de contratos, extrae información de los PDFs asociados, normaliza los códigos CPV mediante un modelo de IA local (Ollama) y filtra las adjudicaciones que coinciden con los códigos CPV de interés definidos por el usuario.

---

## Arquitectura del Pipeline

```
API BOE (sumario diario)
        │
        ▼
┌─────────────────────┐
│  extraccion_datos   │  → Descarga sumario, detecta formalizaciones y extrae datos de PDFs
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ procesamiento_datos │  → Normaliza códigos CPV con IA local (Ollama / qwen2.5:3b)
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│    filtro_datos     │  → Filtra por CPV objetivo, extrae adjudicatarios e importes
└─────────────────────┘
        │
        ▼
  Adjudicaciones_Filtradas/AdjudicatariosYYYYMMDD.json
```

---

## Estructura del Proyecto

```
.
├── consola.py                   # Interfaz Streamlit (punto de entrada)
├── extraccion_datos.py          # Módulo de extracción: API BOE + PDFs
├── procesamiento_datos.py       # Módulo de procesamiento: normalización CPV con Ollama
├── filtro_datos.py              # Módulo de filtrado: CPV objetivo + adjudicatarios
├── filtro_datos_prueba.py       # Script de prueba/desarrollo del módulo de filtrado
├── codigosCPV.csv               # Lista de códigos CPV de interés (requerido)
├── Datos_Brutos/                # JSONs generados tras la extracción (auto-creado)
├── Datos_Procesados/            # JSONs generados tras el procesamiento IA (auto-creado)
└── Adjudicaciones_Filtradas/    # JSONs con resultados finales (auto-creado)
```

---

## Requisitos Previos

### 1. Python
Python **3.9 o superior**.

### 2. Ollama (IA Local)
El módulo de procesamiento requiere [Ollama](https://ollama.com) corriendo localmente con el modelo `qwen2.5:3b`:

```bash
# Instalar Ollama (ver https://ollama.com/download)
ollama pull qwen2.5:3b
ollama serve
```

### 3. Archivo de CPV Objetivo
Crea el archivo `Codigos_CPV_IESMAT.csv` en la raíz del proyecto con el siguiente formato:

```csv
Codigo,Descripcion
72000000-5,Servicios de TI
72212000-4,Servicios de programación de software
```

> La columna `Codigo` debe contener códigos CPV de 8 dígitos. El separador `-` y el dígito de control son opcionales.

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd boe-formalizaciones

# 2. Crear y activar entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Uso

### Interfaz Web (Streamlit)

```bash
streamlit run consola.py
```

Abre el navegador en `http://localhost:8501`. Desde la interfaz puedes:

- **Seleccionar una fecha** en el panel lateral.
- **Ejecutar el pipeline completo** con un solo clic.
- **Visualizar los resultados** de la última ejecución con enlaces directos a los PDFs del BOE.
- **Explorar archivos guardados** de ejecuciones anteriores desde el visor de archivos.
- **Consultar el historial** de la sesión actual.

### Script de Prueba (sin interfaz)

Para probar el módulo de filtrado de forma aislada, edita la fecha en `filtro_datos_prueba.py` y ejecútalo directamente:

```bash
python filtro_datos_prueba.py
```

---

## Descripción de Módulos

### `extraccion_datos.py`
- Conecta con `https://boe.es/datosabiertos/api/boe/sumario/{YYYYMMDD}`.
- Recorre el sumario buscando anuncios de adjudicación/formalización en la Sección 5.
- Descarga cada PDF y extrae los códigos CPV y la descripción mediante expresiones regulares.
- Guarda los resultados en `Datos_Brutos/{YYYYMMDD}.json`.

### `procesamiento_datos.py`
- Recibe los datos brutos y los envía al modelo `qwen2.5:3b` vía Ollama.
- El modelo extrae y normaliza los códigos CPV con temperatura 0 (máxima precisión).
- Guarda los resultados en `Datos_Procesados/{YYYYMMDD}.json`.

### `filtro_datos.py`
- Carga los CPV objetivo desde `Codigos_CPV_IESMAT.csv`.
- Filtra las formalizaciones que contienen al menos un CPV coincidente.
- Descarga de nuevo el PDF para extraer: metadatos, adjudicatarios (NIF, nombre, dirección, PYME) e importes por lote.
- Exporta dos archivos JSON en `Adjudicaciones_Filtradas/`.

### `consola.py`
- Interfaz Streamlit que orquesta los tres módulos anteriores.
- Gestiona el estado de sesión e historial de ejecuciones.
- Muestra resultados agrupados por ID de licitación y lote, con columnas configurables y enlaces a PDFs.

---

## Notas

- El BOE **no publica sumario los domingos**. La aplicación muestra un aviso si se selecciona ese día.
- Si una fecha ya ha sido procesada, se ofrece la opción de re-ejecutar el pipeline para sobreescribir los datos.
- Los lotes con importe inferior a **10.000 €** son excluidos del análisis de adjudicatarios.

---

## Licencia

Uso interno. Consulta con el equipo responsable antes de redistribuir.
