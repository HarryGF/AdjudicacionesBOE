import streamlit as st
import datetime
import pandas as pd
from pathlib import Path

import informe_semanal

st.set_page_config(page_title="Terminal BOE Adjudicaciones", layout="wide")

CONFIGURACION_COLUMNAS = {
    "PDF": st.column_config.LinkColumn(
        "Documento",
        help="Haz clic para abrir el PDF original",
        display_text="Abrir PDF"
    )
}

COLUMNAS_DEFAULT = [
    "ID Anuncio", "Num Lote", "Nombre Adjudicatario", "NIF", "Importe",
    "Localidad", "Pais", "PYME", "Objeto", "CPV Coincidentes", "PDF"
]

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def cargar_csvs_fecha(fecha_str: str) -> pd.DataFrame:
    """Carga Anuncios y Lotes de una fecha y los fusiona para la vista enriquecida."""
    directorio = Path("Adjudicaciones_Filtradas")
    ruta_a = directorio / f"Anuncios_{fecha_str}.csv"
    ruta_b = directorio / f"Lotes_{fecha_str}.csv"

    if not ruta_b.exists():
        return pd.DataFrame()

    df_b = pd.read_csv(ruta_b, encoding="utf-8-sig", dtype=str)

    if ruta_a.exists():
        df_a = pd.read_csv(ruta_a, encoding="utf-8-sig", dtype=str)
        cols_enriquecer = ["ID Anuncio", "Objeto", "Expediente", "CPV Coincidentes", "PDF"]
        df_b = df_b.merge(df_a[cols_enriquecer], on="ID Anuncio", how="left")

    return df_b

def mostrar_datos_agrupados(df: pd.DataFrame, columnas: list):
    """Muestra los datos agrupados visualmente por Formalización -> Lote."""
    cols_validas = [c for c in columnas if c in df.columns]

    if "ID Anuncio" not in df.columns or "Num Lote" not in df.columns:
        st.dataframe(df[cols_validas], width='stretch', hide_index=True, column_config=CONFIGURACION_COLUMNAS)
        return

    for id_anuncio, df_anuncio in df.groupby("ID Anuncio"):
        st.markdown(f"#### Formalización: {id_anuncio}")
        
        # Mostramos metadatos generales si existen (Objeto, Expediente, PDF)
        if "Objeto" in df_anuncio.columns and not pd.isna(df_anuncio["Objeto"].iloc[0]):
            st.caption(f"**Objeto:** {df_anuncio['Objeto'].iloc[0]} | **PDF:** [{id_anuncio}]({df_anuncio['PDF'].iloc[0]})")
            
        for lote, df_lote in df_anuncio.groupby("Num Lote"):
            with st.expander(f"{lote} - Adjudicatario: {df_lote['Nombre Adjudicatario'].iloc[0]}"):
                cols_mostrar = [c for c in cols_validas if c not in ["ID Anuncio", "Num Lote", "Objeto", "Expediente", "PDF", "CPV Coincidentes"]]
                if cols_mostrar:
                    st.dataframe(
                        df_lote[cols_mostrar],
                        width='stretch',
                        hide_index=True,
                        column_config=CONFIGURACION_COLUMNAS
                    )
        st.divider()

with st.sidebar:
    st.title("Terminal BOE AI")
    st.markdown("Gestor de Adjudicaciones")
    st.divider()

    dia = st.date_input("Selecciona la fecha de trabajo", value=datetime.datetime.now())
    fecha_str = dia.strftime("%Y%m%d")
    
    st.divider()
    st.subheader("Navegación")
    seccion = st.radio(
        "Ir a:",
        ["Dashboard Diario", "Explorador Histórico", "Informe Semanal"],
        label_visibility="collapsed"
    )

if seccion == "Dashboard Diario":
    st.title("Adjudicaciones del Día")
    st.markdown(f"Resultados de la extracción automatizada para el **{dia.strftime('%d/%m/%Y')}**.")
    st.divider()

    if dia.weekday() == 6:
        st.warning("El Boletín Oficial del Estado no publica sumarios los domingos.")
    else:
        df_hoy = cargar_csvs_fecha(fecha_str)
        
        if not df_hoy.empty:
            st.metric(label="Lotes Adjudicados Capturados", value=len(df_hoy))
            st.subheader("Datos de Adjudicación")
            mostrar_datos_agrupados(df_hoy, COLUMNAS_DEFAULT)
        else:
            st.info("Aún no se han extraído los datos o no hay adjudicaciones coincidentes para este día.")

elif seccion == "Explorador Histórico":
    st.title("Explorador de Archivos")
    st.markdown("Navega por las carpetas del sistema para revisar cualquier archivo en crudo, procesado o final.")
    st.divider()

    rutas = ["Adjudicaciones_Filtradas", "Datos_Procesados", "Datos_Brutos"]
    
    col1, col2 = st.columns(2)
    with col1:
        carpeta_seleccionada = st.selectbox("1. Selecciona el directorio", options=rutas)
        carpeta = Path(carpeta_seleccionada)
    
    options = [archivo.stem for archivo in carpeta.glob("*.csv")] if carpeta.exists() and carpeta.is_dir() else []
    options.sort(reverse=True)

    with col2:
        if options:
            doc_seleccionado = st.selectbox("2. Selecciona el archivo", options=options)
        else:
            st.selectbox("2. Selecciona el archivo", options=["Carpeta vacía"], disabled=True)
            doc_seleccionado = None

    if doc_seleccionado:
        ruta_archivo = carpeta / f"{doc_seleccionado}.csv"
        try:
            df_visor = pd.read_csv(ruta_archivo, encoding="utf-8-sig", dtype=str)
            columnas = df_visor.columns.tolist()
            
            default_cols = [c for c in COLUMNAS_DEFAULT if c in columnas]
            columnas_seleccionadas = st.multiselect(
                "Filtro de columnas a visualizar:",
                options=columnas,
                default=default_cols if default_cols else columnas
            )

            if not df_visor.empty and columnas_seleccionadas:
                st.dataframe(
                    df_visor[columnas_seleccionadas], 
                    width='stretch',
                    column_config=CONFIGURACION_COLUMNAS,
                    hide_index=True if carpeta_seleccionada != "Datos_Procesados" else False
                )
                
                csv_bytes = df_visor[columnas_seleccionadas].to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="Descargar tabla actual (CSV)",
                    data=csv_bytes,
                    file_name=f"exportacion_{doc_seleccionado}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Selecciona al menos una columna para mostrar los datos.")
        except Exception as e:
            st.error(f"No se pudo cargar el archivo: {e}")

elif seccion == "Informe Semanal":
    st.title("Informe Semanal")
    st.markdown(f"Consolida todas las adjudicaciones capturadas en la semana de la fecha: **{dia.strftime('%d/%m/%Y')}**.")
    st.divider()

    if st.button("Generar Informe de esta Semana", type="primary"):
        with st.spinner("Compilando datos de la semana..."):
            datos_semana = informe_semanal.generar_informe_semana(dia)
            
        if datos_semana and (datos_semana.get("anuncios") or datos_semana.get("lotes")):
            st.success("Informe generado correctamente.")
            
            sub_a, sub_b = st.tabs(["Anuncios (Cabeceras)", "Lotes (Adjudicatarios)"])
            
            with sub_a:
                df_anuncios = pd.DataFrame(datos_semana.get("anuncios", []))
                if not df_anuncios.empty:
                    st.dataframe(
                        df_anuncios, 
                        width='stretch', 
                        hide_index=True,
                        column_config=CONFIGURACION_COLUMNAS
                    )
                    st.download_button(
                        label="Descargar Anuncios (CSV)",
                        data=df_anuncios.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"informe_anuncios_{dia.strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Sin anuncios esta semana.")
            
            with sub_b:
                df_lotes = pd.DataFrame(datos_semana.get("lotes", []))
                if not df_lotes.empty:
                    if not df_anuncios.empty:
                        cols_enriquecer = ["ID Anuncio", "Objeto", "Expediente", "CPV Coincidentes", "PDF"]
                        df_lotes_enriquecido = df_lotes.merge(df_anuncios[cols_enriquecer], on="ID Anuncio", how="left")
                    else:
                        df_lotes_enriquecido = df_lotes
                        
                    mostrar_datos_agrupados(df_lotes_enriquecido, COLUMNAS_DEFAULT)
                    
                    st.download_button(
                        label="Descargar Lotes (CSV)",
                        data=df_lotes.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"informe_lotes_{dia.strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Sin lotes esta semana.")
        else:
            st.warning("No hay datos procesados para generar el informe de esta semana.")