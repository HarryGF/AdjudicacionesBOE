import streamlit as st
import datetime
import pandas as pd
import json
import time
from pathlib import Path

# Importaciones de tu pipeline
import extraccion_datos
import procesamiento_datos
import filtro_datos

st.set_page_config(page_title="BOE Formalizaciones", layout="wide")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE COLUMNAS
# ══════════════════════════════════════════════════════════════════════════════
CONFIGURACION_COLUMNAS = {
    "PDF": st.column_config.LinkColumn(
        "Documento",
        help="Haz clic para abrir el PDF original",
        display_text="Abrir PDF" 
    )
}

CARPETAS = ["Adjudicaciones_Filtradas", "Datos_Procesados", "Datos_Brutos"]

COLUMNAS_DEFAULT = [
    "NIF", "Nombre Adjudicatario", "Importe",
    "Localidad", "Codigo Postal", "Pais", "PYME", "Expediente", 
    "Objeto", "CPV Coincidentes", "PDF"
]

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════
def cargar_json_a_dataframe(data_json):
    if not data_json:
        return pd.DataFrame()
        
    filas = []
    if isinstance(data_json, list):
        return pd.DataFrame(data_json)
        
    for id_licitacion, datos_id in data_json.items():
        if not isinstance(datos_id, dict): continue
            
        if "Objeto" in datos_id or "Expediente" in datos_id:
            fila = {"ID Licitación": id_licitacion}
            for k, v in datos_id.items():
                fila[k] = ", ".join(v) if isinstance(v, list) else v
            filas.append(fila)
        else:
            for lote, datos_lote in datos_id.items():
                if isinstance(datos_lote, dict):
                    fila = {"ID Licitación": id_licitacion, "Lote": lote}
                    fila.update(datos_lote)
                    filas.append(fila)
                    
    return pd.DataFrame(filas)

def mostrar_datos_agrupados(df, columnas):
    """Muestra los datos agrupados aplicando la configuración de LinkColumn"""
    cols_validas = [c for c in columnas if c in df.columns]
    
    if "Lote" not in df.columns or "ID Licitación" not in df.columns:
        st.dataframe(
            df[cols_validas], 
            width='stretch', 
            hide_index=True, 
            column_config=CONFIGURACION_COLUMNAS 
        )
        return

    for id_lic, df_id in df.groupby("ID Licitación"):
        st.markdown(f"#### Formalización: {id_lic}")
        for lote, df_lote in df_id.groupby("Lote"):
            st.info(f"**{lote}**")
            cols_mostrar = [c for c in cols_validas if c not in ["ID Licitación", "Lote"]]
            if cols_mostrar:
                st.dataframe(
                    df_lote[cols_mostrar], 
                    width='stretch', 
                    hide_index=True, 
                    column_config=CONFIGURACION_COLUMNAS
                )
        st.divider()

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
        opciones_archivo = sorted([f.stem for f in carpeta.glob("*.json")], reverse=True)
        if opciones_archivo:
            doc_seleccionado = st.selectbox("Archivos guardados", options=opciones_archivo)
            ruta_archivo = carpeta / f"{doc_seleccionado}.json"
            try:
                with open(ruta_archivo, "r", encoding="utf-8") as f:
                    data_json = json.load(f)
                df_visor = cargar_json_a_dataframe(data_json)
                todas_columnas = df_visor.columns.tolist()
                default_cols = [c for c in COLUMNAS_DEFAULT if c in todas_columnas]
                columnas_seleccionadas = st.multiselect("Columnas:", options=todas_columnas, default=default_cols)
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Carpeta no encontrada.")

# ══════════════════════════════════════════════════════════════════════════════
# CUERPO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
st.title("BOE Formalizaciones")
st.markdown("Pipeline de extracción y filtrado de contratos adjudicados del BOE.")

fecha_str = dia.strftime("%Y%m%d")
ruta_resultado = Path("Adjudicaciones_Filtradas") / f"Adjudicatarios{fecha_str}.json"

if dia.weekday() == 6:
    st.warning("El BOE no publica sumario los domingos. Elige otra fecha.")
    st.stop()

col_info, col_btn = st.columns([3, 1])
with col_info:
    st.info(f"Fecha seleccionada: **{dia.strftime('%d/%m/%Y')}**")
with col_btn:
    if ruta_resultado.exists():
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
        datos_brutos = resultado_extraccion["datos"]

        st.write("Normalizando códigos CPV con IA local (Ollama)...")
        resultado_procesamiento = procesamiento_datos.ejecutar_procesamiento(fecha_str, datos_brutos)
        if resultado_procesamiento["status"] == "error":
            status.update(label="Error en el procesamiento IA", state="error")
            st.error(resultado_procesamiento["mensaje"]); st.stop()
        datos_procesados = resultado_procesamiento["datos"]

        st.write("Filtrando por CPV objetivo y extrayendo adjudicatarios...")
        resultado_filtrado = filtro_datos.filtrado_formalizaciones(fecha_str, datos_procesados)
        if resultado_filtrado["status"] == "error":
            status.update(label="Error en el filtrado", state="error")
            st.error(resultado_filtrado["mensaje"]); st.stop()
        if resultado_filtrado.get("cantidad", 0) == 0:
            status.update(label="Sin coincidencias CPV", state="complete")
            st.info("Ninguna formalización coincide con los CPV objetivo."); st.stop()

        with open(ruta_resultado, "r", encoding="utf-8") as f:
            datos_finales_brutos = json.load(f)

        df_resultado = cargar_json_a_dataframe(datos_finales_brutos)

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
        cols_mostrar = [c for c in COLUMNAS_DEFAULT if c in df_res.columns]
        mostrar_datos_agrupados(df_res, cols_mostrar)
    else:
        st.warning("No hay datos para mostrar.")
else:
    st.warning("Ejecute el programa.")

# ══════════════════════════════════════════════════════════════════════════════
# OTRAS FUNCIONALIDADES
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
tab_visor, tab_historial = st.tabs(["Visor de Archivos", "Historial de la Sesión"])

with tab_visor:
    if not df_visor.empty and columnas_seleccionadas:
        st.subheader(f"Archivo: {doc_seleccionado}")
        # LLAMADA CORRECTA: Solo llamamos a la función, no asignamos a df_visor
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