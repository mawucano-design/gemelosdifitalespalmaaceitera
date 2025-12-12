import streamlit as st
import geopandas as gpd
from shapely.geometry import Polygon
from datetime import datetime

# Importar funciones desde los módulos organizados
from src.utils.ui_helpers import (
    mostrar_modo_demo,
    mostrar_configuracion_parcela,
    mostrar_resultados_principales,
    mostrar_resultados_textura
)
from src.data.file_loader import procesar_archivo
from src.utils.constants import PARAMETROS_CULTIVOS

# Configuración de la página
st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - METODOLOGÍA GEE COMPLETA CON AGROECOLOGÍA")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    cultivo = st.selectbox("Cultivo:", ["PALMA_ACEITERA", "CACAO", "BANANO"])
    analisis_tipo = st.selectbox("Tipo de Análisis:", ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK", "ANÁLISIS DE TEXTURA"])
    nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    mes_analisis = st.selectbox("Mes de Análisis:", [
        "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
        "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
    ])
    st.subheader("🎯 División de Parcela")
    n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=32, value=24)
    st.subheader("📤 Subir Parcela")
    uploaded_file = st.file_uploader("Subir ZIP con shapefile o archivo KML de tu parcela", type=['zip', 'kml'])
    
    if st.button("🔄 Reiniciar Análisis"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Inicializar session_state si no existe
if 'analisis_completado' not in st.session_state:
    st.session_state.analisis_completado = False
if 'gdf_original' not in st.session_state:
    st.session_state.gdf_original = None
if 'datos_demo' not in st.session_state:
    st.session_state.datos_demo = False

# Guardar configuración en session_state para uso en módulos
st.session_state.cultivo = cultivo
st.session_state.analisis_tipo = analisis_tipo
st.session_state.nutriente = nutriente
st.session_state.mes_analisis = mes_analisis
st.session_state.n_divisiones = n_divisiones

# Procesar archivo subido
if uploaded_file is not None and not st.session_state.analisis_completado:
    with st.spinner("🔄 Procesando archivo..."):
        gdf_original = procesar_archivo(uploaded_file)
        if gdf_original is not None:
            st.session_state.gdf_original = gdf_original
            st.session_state.datos_demo = False

# Cargar datos de demostración
if st.session_state.datos_demo and st.session_state.gdf_original is None:
    poligono_ejemplo = Polygon([
        [-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], [-74.1, 4.7], [-74.1, 4.6]
    ])
    gdf_demo = gpd.GeoDataFrame(
        {'id': [1], 'nombre': ['Parcela Demo']},
        geometry=[poligono_ejemplo],
        crs="EPSG:4326"
    )
    st.session_state.gdf_original = gdf_demo

# Mostrar interfaz según estado
if st.session_state.analisis_completado:
    if analisis_tipo == "ANÁLISIS DE TEXTURA":
        mostrar_resultados_textura()
    else:
        tab1, tab2 = st.tabs(["📊 Análisis Principal", "🏗️ Análisis de Textura"])
        with tab1:
            mostrar_resultados_principales()
        with tab2:
            if st.session_state.get('analisis_textura') is not None:
                mostrar_resultados_textura()
            else:
                st.info("Ejecuta el análisis principal para obtener datos de textura")
elif st.session_state.gdf_original is not None:
    mostrar_configuracion_parcela()
else:
    mostrar_modo_demo()

# Información adicional en sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Métodología GEE")
st.sidebar.info("""
Esta aplicación utiliza:
- **Google Earth Engine** para análisis satelital
- **Índices espectrales** (NDVI, etc.)
- **Modelos predictivos** de nutrientes
- **Análisis de textura** del suelo
- **Enfoque agroecológico** integrado
- **OpenStreetMap** como base cartográfica
""")
