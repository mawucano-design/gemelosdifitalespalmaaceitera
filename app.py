import streamlit as st
import geopandas as gpd
import tempfile
import os
from shapely.geometry import Polygon
from datetime import datetime

# Importar desde módulos organizados
from src.utils.ui_helpers import (
    mostrar_modo_demo,
    mostrar_configuracion_parcela,
    mostrar_resultados_principales,
    mostrar_resultados_textura
)
from src.data.file_loader import procesar_archivo
from src.models.tree_segmentation import detect_trees_from_image, boxes_to_geojson
from src.digital_twin.tree_registry import TreeRegistry

# Configuración de la página
st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - DIGITAL TWIN + AGROECOLOGÍA")
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
    uploaded_file = st.file_uploader("Subir ZIP con shapefile o archivo KML", type=['zip', 'kml'])
    st.subheader("📸 (Opcional) Imagen de Drone")
    drone_image = st.file_uploader("Subir imagen JPG/PNG del drone", type=['jpg', 'jpeg', 'png'])
    
    if st.button("🔄 Reiniciar Análisis"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Inicializar session_state
if 'analisis_completado' not in st.session_state:
    st.session_state.analisis_completado = False
if 'gdf_original' not in st.session_state:
    st.session_state.gdf_original = None
if 'datos_demo' not in st.session_state:
    st.session_state.datos_demo = False

# Guardar configuración
st.session_state.cultivo = cultivo
st.session_state.analisis_tipo = analisis_tipo
st.session_state.nutriente = nutriente
st.session_state.mes_analisis = mes_analisis
st.session_state.n_divisiones = n_divisiones

# Procesar archivo principal (shapefile/KML)
if uploaded_file is not None and not st.session_state.analisis_completado:
    with st.spinner("🔄 Procesando parcela..."):
        gdf_original = procesar_archivo(uploaded_file)
        if gdf_original is not None:
            st.session_state.gdf_original = gdf_original
            st.session_state.datos_demo = False

# Cargar datos de demo si se pide
if st.session_state.datos_demo and st.session_state.gdf_original is None:
    poligono_ejemplo = Polygon([[-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], [-74.1, 4.7]])
    gdf_demo = gpd.GeoDataFrame({'id': [1]}, geometry=[poligono_ejemplo], crs="EPSG:4326")
    st.session_state.gdf_original = gdf_demo

# Calcular área total
if st.session_state.gdf_original is not None:
    from src.data.file_loader import calcular_superficie
    st.session_state.area_total = float(calcular_superficie(st.session_state.gdf_original).sum())
else:
    st.session_state.area_total = 0.0

# Ejecutar análisis
if st.session_state.gdf_original is not None and not st.session_state.analisis_completado:
    gdf_original = st.session_state.gdf_original
    gdf_zonas = None

    # Si se subió imagen de drone → detección por árboles
    if drone_image is not None and cultivo == "PALMA_ACEITERA":
        with st.spinner("🔍 Detectando árboles individuales con Vision AI..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(drone_image.getvalue())
                boxes = detect_trees_from_image(tmp.name, cultivo)
            if boxes:
                gdf_zonas = boxes_to_geojson(boxes, gdf_original.crs)
                st.success(f"✅ Detectados {len(boxes)} árboles individuales")
                # Registrar en Digital Twin
                registry = TreeRegistry()
                tree_ids = registry.register_trees_from_boxes(boxes, parcela_id="demo_001")
                st.session_state.tree_registry = registry
                st.session_state.tree_ids = tree_ids
            else:
                st.warning("⚠️ No se detectaron árboles. Usando división en zonas.")
                gdf_zonas = None

    # Si no hay drone o no hay detección → usar zonas
    if gdf_zonas is None:
        from src.core.division_zonas import dividir_parcela_en_zonas
        with st.spinner("🔄 Dividiendo parcela en zonas de manejo..."):
            gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)

    # Ejecutar análisis principal
    with st.spinner("🔬 Analizando fertilidad y textura..."):
        from src.core.indices_gee import calcular_indices_gee
        from src.data.textura_suelo import analizar_textura_suelo

        if analisis_tipo == "ANÁLISIS DE TEXTURA":
            gdf_textura = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
            st.session_state.analisis_textura = gdf_textura
        else:
            gdf_fert = calcular_indices_gee(gdf_zonas, cultivo, mes_analisis, analisis_tipo, nutriente)
            st.session_state.gdf_analisis = gdf_fert
            gdf_textura = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
            st.session_state.analisis_textura = gdf_textura

        st.session_state.analisis_completado = True
        st.rerun()

# Mostrar resultados
if st.session_state.analisis_completado:
    if analisis_tipo == "ANÁLISIS DE TEXTURA":
        mostrar_resultados_textura(cultivo, mes_analisis, st.session_state.area_total)
    else:
        tab1, tab2 = st.tabs(["📊 Análisis Principal", "🏗️ Análisis de Textura"])
        with tab1:
            mostrar_resultados_principales(cultivo, analisis_tipo, nutriente, mes_analisis, st.session_state.area_total)
        with tab2:
            if st.session_state.analisis_textura is not None:
                mostrar_resultados_textura(cultivo, mes_analisis, st.session_state.area_total)
            else:
                st.info("Ejecuta el análisis principal para obtener datos de textura")
elif st.session_state.gdf_original is not None:
    mostrar_configuracion_parcela(cultivo, n_divisiones)
else:
    mostrar_modo_demo()

# Información en sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 🌴 Digital Twin + Agroecología")
st.sidebar.info("""
**Fase 2 en desarrollo:**
- 📸 Detección de árboles por Vision AI
- 🌿 Análisis individual por árbol
- 📊 Fusión con datos multiespectrales
- 🔄 Sincronización con ERP (futuro)

**Base actual:** análisis por zonas + agroecología
""")

# Aviso si hay Digital Twin activo
if 'tree_ids' in st.session_state:
    st.sidebar.success(f"🌳 Digital Twin: {len(st.session_state.tree_ids)} árboles registrados")
