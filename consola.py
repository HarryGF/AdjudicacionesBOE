import streamlit as st
import datetime
import pandas as pd
import time
from pathlib import Path

import extraccion_datos
import procesamiento_datos
import filtro_datos
import informe_semanal

st.set_page_config(page_title="BOE Formalizaciones", layout="wide")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
CONFIGURACION_COLUMNAS = {
    "PDF": st.column_config.LinkColumn(
        "Documento",
        help="Haz clic para abrir el PDF original",
        display_text="Abrir PDF"
    )
}

CARPETAS = ["Adjudicaciones_Filtradas", "Datos_Procesados", "Datos_Brutos"]

# Columnas del CSV mergeado (Tabla_B + campos de Tabla_A)
COLUMNAS_DEFAULT = [
    "ID Anuncio", "Num Lote", "Nombre Adjudicatario", "NIF", "Importe",
    "Localidad", "Pais", "PYME", "Objeto", "CPV Coincidentes", "PDF"
]

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════
def cargar_csvs_fecha(fecha_str: str) -> pd.DataFrame:
    """Carga Tabla_A y Tabla_B de una fecha y las mergea en un único DataFrame."""
    directorio = Path("Adjudicaciones_Filtradas")
    ruta_a = directorio / f"Anuncios_{fecha_str}.csv"
    ruta_b = directorio / f"Lotes_{fecha_str}.csv"

    if not ruta_b.exists():
        return pd.DataFrame()

    df_b = pd.read_csv(ruta_b, encoding="utf-8-sig")

    if ruta_a.exists():
        df_a = pd.read_csv(ruta_a, encoding="utf-8-sig")
        # Añadimos Objeto, Expediente, CPV y PDF al DataFrame de lotes
        cols_enriquecer = ["ID Anuncio", "Objeto", "Expediente", "CPV Coincidentes", "PDF"]
        df_b = df_b.merge(df_a[cols_enriquecer], on="ID Anuncio", how="left")

    return df_b

def cargar_csv_sidebar(ruta: Path) -> pd.DataFrame:
    """Carga cualquier CSV del explorador de la sidebar."""
    try:
        return pd.read_csv(ruta, encoding="utf-8-sig")
    except Exception as e:
        st.error(f"Error al leer CSV: {e}")
        return pd.DataFrame()

def mostrar_datos_agrupados(df: pd.DataFrame, columnas: list):
    """Muestra los datos agrupados por anuncio y lote."""
    cols_validas = [c for c in columnas if c in df.columns]

    # Si no tiene las columnas de agrupación, muestra plano
    if "ID Anuncio" not in df.columns or "Num Lote" not in df.columns:
        st.dataframe(
            df[cols_validas],
            width='stretch',
            hide_index=True,
            column_config=CONFIGURACION_COLUMNAS
        )
        return

    for id_anuncio, df_anuncio in df.groupby("ID Anuncio"):
        st.markdown(f"#### Formalización: {id_anuncio}")
        for lote, df_lote in df_anuncio.groupby("Num Lote"):
            st.info(f"**{lote}**")
            cols_mostrar = [c for c in cols_validas if c not in ["ID Anuncio", "Num Lote"]]
            if cols_mostrar:
                st.dataframe(
                    df_lote[cols_mostrar],
                    width='stretch',
                    hide_index=True,
                    column_config=CONFIGURACION_COLUMNAS
                )
        st.divider()

def rutas_resultado_existen(fecha_str: str) -> bool:
    directorio = Path("Adjudicaciones_Filtradas")
    return (directorio / f"Lotes_{fecha_str}.csv").exists()

# ══════════════════════════════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ══════════════════════════════════════════════════════════════════════════════
if "historial" not in st.session_state:
    st.session_state.historial = {}
if "ultimo_resultado" not in st.session_state:
    st.session_state.ultimo_resultado = None
if "ultima_fecha" not in st.session_state:
    st.session_state.ultima_fecha = None

# ══════════════════════════════════════════════════════════════════════════════
# BARRA LATERAL
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("Ajustes")
    dia = st.date_input("Elige día", value=datetime.datetime.now())
    st.divider()

    st.subheader("Explorador de Archivos")
    carpeta_seleccionada = st.selectbox("Carpeta", options=CARPETAS)
    carpeta = Path(carpeta_seleccionada)

    df_visor = pd.DataFrame()
    columnas_seleccionadas = []
    doc_seleccionado = None

    if carpeta.exists() and carpeta.is_dir():
        opciones_archivo = sorted([f.stem for f in carpeta.glob("*.csv")], reverse=True)
        if opciones_archivo:
            doc_seleccionado = st.selectbox("Archivos guardados", options=opciones_archivo)
            ruta_archivo = carpeta / f"{doc_seleccionado}.csv"
            df_visor = cargar_csv_sidebar(ruta_archivo)
            if not df_visor.empty:
                todas_columnas = df_visor.columns.tolist()
                default_cols = [c for c in COLUMNAS_DEFAULT if c in todas_columnas]
                columnas_seleccionadas = st.multiselect(
                    "Columnas:", options=todas_columnas, default=default_cols
                )
    else:
        st.warning("Carpeta no encontrada.")

# ══════════════════════════════════════════════════════════════════════════════
# CUERPO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
st.title("BOE Formalizaciones")
st.markdown("Pipeline de extracción y filtrado de contratos adjudicados del BOE.")

fecha_str = dia.strftime("%Y%m%d")

if dia.weekday() == 6:
    st.warning("El BOE no publica sumario los domingos. Elige otra fecha.")
    st.stop()

col_info, col_btn = st.columns([3, 1])
with col_info:
    st.info(f"Fecha seleccionada: **{dia.strftime('%d/%m/%Y')}**")
with col_btn:
    if rutas_resultado_existen(fecha_str):
        st.warning("Esta fecha ya está procesada.")
        ejecutar = st.button("Re-Ejecutar Pipeline", type="secondary", width='stretch')
    else:
        ejecutar = st.button("Ejecutar Pipeline", type="primary", width='stretch')

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
if ejecutar:
    with st.status("Ejecutando Pipeline...", expanded=True) as status:

        st.write(f"Conectando a la API del BOE para el **{fecha_str}**...")
        resultado_extraccion = extraccion_datos.ejecutar_extraccion(fecha_str)
        if resultado_extraccion["status"] == "error":
            status.update(label="Error en la extracción", state="error")
            st.error(resultado_extraccion["mensaje"]); st.stop()
        if resultado_extraccion.get("cantidad", 0) == 0:
            status.update(label="Sin formalizaciones hoy", state="complete")
            st.success("No se han encontrado anuncios de adjudicación para esta fecha."); st.stop()

        st.write("Normalizando códigos CPV con IA local (Ollama)...")
        resultado_procesamiento = procesamiento_datos.ejecutar_procesamiento(
            fecha_str, resultado_extraccion["datos"]
        )
        if resultado_procesamiento["status"] == "error":
            status.update(label="Error en el procesamiento IA", state="error")
            st.error(resultado_procesamiento["mensaje"]); st.stop()

        st.write("Filtrando por CPV objetivo y extrayendo adjudicatarios...")
        resultado_filtrado = filtro_datos.filtrado_formalizaciones(
            fecha_str, resultado_procesamiento["datos"]
        )
        if resultado_filtrado["status"] == "error":
            status.update(label="Error en el filtrado", state="error")
            st.error(resultado_filtrado["mensaje"]); st.stop()
        if resultado_filtrado.get("anuncios", 0) == 0:
            status.update(label="Sin coincidencias CPV", state="complete")
            st.info("Ninguna formalización coincide con los CPV objetivo."); st.stop()

        # Cargamos el resultado mergeando los dos CSV generados
        df_resultado = cargar_csvs_fecha(fecha_str)
        st.session_state.ultimo_resultado = df_resultado
        st.session_state.ultima_fecha = fecha_str
        st.session_state.historial[fecha_str] = df_resultado
        status.update(label="Pipeline completado con éxito", state="complete", expanded=False)

    st.toast(f"¡Datos del {fecha_str} guardados correctamente!")
    time.sleep(1)
    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RESULTADO DE LA ÚLTIMA EJECUCIÓN
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.ultimo_resultado is not None:
    st.divider()
    df_res = st.session_state.ultimo_resultado
    st.subheader(f"Resultado del {st.session_state.ultima_fecha}")
    if not df_res.empty:
        mostrar_datos_agrupados(df_res, COLUMNAS_DEFAULT)
    else:
        st.warning("No hay datos para mostrar.")
else:
    st.warning("Ejecute el programa.")

# ══════════════════════════════════════════════════════════════════════════════
# PESTAÑAS
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
tab_visor, tab_historial, tab_semana = st.tabs(
    ["Visor de Archivos", "Historial de la Sesión", "Informe Semanal"]
)

with tab_visor:
    if not df_visor.empty and columnas_seleccionadas:
        st.subheader(f"Archivo: {doc_seleccionado}")
        mostrar_datos_agrupados(df_visor, columnas_seleccionadas)
    else:
        st.info("Selecciona un archivo para visualizarlo.")

with tab_historial:
    if st.session_state.historial:
        for f, df_h in st.session_state.historial.items():
            with st.expander(f"Fecha {f}"):
                mostrar_datos_agrupados(df_h, COLUMNAS_DEFAULT)
    else:
        st.warning("Aún no se ha ejecutado el programa.")

with tab_semana:
    if st.button("Generar informe de esta semana"):
        datos_semana = informe_semanal.generar_informe_semana()
        if datos_semana:
            # Mostramos anuncios y lotes en subtabs separados
            sub_a, sub_b = st.tabs(["Anuncios", "Lotes"])
            with sub_a:
                df_anuncios = pd.DataFrame(datos_semana.get("anuncios", []))
                if not df_anuncios.empty:
                    st.dataframe(df_anuncios, width='stretch', hide_index=True,
                                 column_config=CONFIGURACION_COLUMNAS)
                else:
                    st.info("Sin anuncios esta semana.")
            with sub_b:
                df_lotes = pd.DataFrame(datos_semana.get("lotes", []))
                if not df_lotes.empty:
                    mostrar_datos_agrupados(df_lotes, COLUMNAS_DEFAULT)
                else:
                    st.info("Sin lotes esta semana.")
        else:
            st.warning("No hay datos para esta semana.")