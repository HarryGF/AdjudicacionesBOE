import streamlit as st
import datetime
import pandas as pd
from pathlib import Path

# Solo importamos el informe semanal, nada de extracción pesada
import informe_semanal

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

COLUMNAS_DEFAULT = [
    "ID Anuncio", "Num Lote", "Nombre Adjudicatario", "NIF", "Importe",
    "Localidad", "Pais", "PYME", "Objeto", "CPV Coincidentes", "PDF"
]

# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════
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

st.set_page_config(page_title="Terminal BOE Adjudicaciones", layout="wide")

st.title("BOE Adjudicaciones - Visor de Datos")
st.markdown("Terminal de visualización para adjudicaciones extraídas y filtradas automáticamente.")

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
        st.warning(f"La carpeta '{carpeta_seleccionada}' está vacía o no existe.")

# ══════════════════════════════════════════════════════════════════════════════
# CUERPO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
fecha_str = dia.strftime("%Y%m%d")

# Comprobación de Domingo e información de estado
if dia.weekday() == 6:
    st.warning("El Boletín Oficial del Estado no publica sumario los domingos. Elige otra fecha en el panel izquierdo.")
else:
    if rutas_resultado_existen(fecha_str):
        st.success(f"Los datos de adjudicación del día **{dia.strftime('%d/%m/%Y')}** están procesados y listos para visualizar.")
    else:
        st.info(f"El proceso automatizado aún no ha extraído las adjudicaciones del día **{dia.strftime('%d/%m/%Y')}**.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# PESTAÑAS PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════════
tab_visor, tab_semana = st.tabs(["Visor de Archivos", "Informe Semanal"])

with tab_visor:
    st.subheader("Datos del archivo seleccionado")
    if not df_visor.empty and columnas_seleccionadas:
        m1, m2 = st.columns(2)
        m1.metric("Registros Totales", len(df_visor))
        
        # Aprovechamos tu excelente función de agrupamiento
        mostrar_datos_agrupados(df_visor, columnas_seleccionadas)
        
        # Botón de descarga
        csv_bytes = df_visor[columnas_seleccionadas].to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="Descargar tabla como CSV",
            data=csv_bytes,
            file_name=f"exportacion_{doc_seleccionado}.csv",
            mime="text/csv",
        )
    elif not df_visor.empty and not columnas_seleccionadas:
        st.warning("Selecciona al menos una columna en la barra lateral para mostrar los datos.")
    else:
        st.info("Selecciona un archivo en el panel lateral para visualizarlo aquí.")

with tab_semana:
    if st.button("Generar informe de esta semana"):
        datos_semana = informe_semanal.generar_informe_semana(dia)
        if datos_semana:
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
                    
                    st.download_button(
                        label="Descargar lotes como CSV",
                        data=df_lotes.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"informe_lotes_{dia.strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Sin lotes esta semana.")
        else:
            st.warning("No hay datos procesados para esta semana.")