import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import io
from shapely.geometry import Polygon
import math
import folium
from folium import plugins
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import fiona
import requests

# Configuración de la página de Streamlit
st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
st.title("🌱 ANALIZADOR CULTIVOS - DIGITAL TWIN CON NASA POWER + PLANETSCOPE")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# ============================================================================
# PARÁMETROS MEJORADOS Y MÁS REALISTAS PARA DIFERENTES CULTIVOS
# ============================================================================
PARAMETROS_CULTIVOS = {
    'PALMA_ACEITERA': {
        'NITROGENO': {'min': 120, 'max': 200, 'optimo': 160},
        'FOSFORO': {'min': 40, 'max': 80, 'optimo': 60},
        'POTASIO': {'min': 160, 'max': 240, 'optimo': 200},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.35,
        'pH_OPTIMO': 5.5,
        'CONDUCTIVIDAD_OPTIMA': 1.2
    },
    'CACAO': {
        'NITROGENO': {'min': 100, 'max': 180, 'optimo': 140},
        'FOSFORO': {'min': 30, 'max': 60, 'optimo': 45},
        'POTASIO': {'min': 120, 'max': 200, 'optimo': 160},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.4,
        'pH_OPTIMO': 6.0,
        'CONDUCTIVIDAD_OPTIMA': 1.0
    },
    'BANANO': {
        'NITROGENO': {'min': 180, 'max': 280, 'optimo': 230},
        'FOSFORO': {'min': 50, 'max': 90, 'optimo': 70},
        'POTASIO': {'min': 250, 'max': 350, 'optimo': 300},
        'MATERIA_ORGANICA_OPTIMA': 4.5,
        'HUMEDAD_OPTIMA': 0.45,
        'pH_OPTIMO': 6.2,
        'CONDUCTIVIDAD_OPTIMA': 1.5
    }
}

# ============================================================================
# FUNCIONES DE DATOS CLIMÁTICOS Y PLANETSCOPE
# ============================================================================

def obtener_datos_nasa_power(lat, lon, mes_analisis):
    """Obtiene datos climáticos de NASA POWER"""
    try:
        # Mapear mes a número
        mes_num = {
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
            "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
        }[mes_analisis]
        
        año = datetime.now().year
        start = f"{año}{mes_num:02d}01"
        end = f"{año}{mes_num+1:02d}01" if mes_num < 12 else f"{año+1}0101"
        
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,PRECTOTCORR,WS10M",
            "community": "ag",
            "longitude": lon,
            "latitude": lat,
            "start": start,
            "end": end,
            "format": "json"
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            dias = data['properties']['parameter']
            rad_solar = np.nanmean(list(dias['ALLSKY_SFC_SW_DWN'].values()))
            precip = np.nanmean(list(dias['PRECTOTCORR'].values()))
            viento = np.nanmean(list(dias['WS10M'].values()))
            
            return {
                'radiacion_solar': float(rad_solar) if not np.isnan(rad_solar) else 16.0,
                'precipitacion': float(precip) if not np.isnan(precip) else 6.0,
                'velocidad_viento': float(viento) if not np.isnan(viento) else 2.5
            }
    except:
        # Valores por defecto (Colombia promedio)
        return {
            'radiacion_solar': 16.0,  # MJ/m²/día
            'precipitacion': 6.0,     # mm/día
            'velocidad_viento': 2.5   # m/s
        }

def obtener_datos_planetscope(lat, lon, api_key=None):
    """Obtiene o simula datos de PlanetScope"""
    if api_key:
        # Aquí iría la integración real con Planet API
        # Por ahora, simulamos datos realistas
        pass
    
    # Simular datos basados en coordenadas (zonas tropicales)
    np.random.seed(abs(hash(f"{lat:.4f}_{lon:.4f}")) % (2**32))
    ndvi = np.clip(0.6 + np.random.normal(0, 0.1), 0.3, 0.9)
    evi = np.clip(0.4 + np.random.normal(0, 0.08), 0.2, 0.7)
    lai = np.clip(4.0 + np.random.normal(0, 0.8), 1.0, 8.0)  # Leaf Area Index
    
    return {
        'ndvi_planetscope': ndvi,
        'evi_planetscope': evi,
        'lai_planetscope': lai
    }

def calcular_potencial_cosecha(gdf_analisis, datos_clima, datos_planetscope, cultivo):
    """Calcula potencial de cosecha usando suelo + clima + satélite"""
    if cultivo != "PALMA_ACEITERA":
        gdf_analisis['potencial_cosecha'] = 0.0
        return gdf_analisis
    
    # Factores climáticos
    rad_solar = datos_clima['radiacion_solar']
    precip_mensual = datos_clima['precipitacion'] * 30
    viento = datos_clima['velocidad_viento']
    
    factor_rad = min(1.0, rad_solar / 20.0)
    factor_agua = min(1.0, precip_mensual / 200.0)
    factor_viento = max(0.7, 1.0 - (viento - 2.0) / 10.0)
    
    # Factor de satélite (NDVI mejora la fotosíntesis)
    ndvi = datos_planetscope['ndvi_planetscope']
    factor_ndvi = min(1.0, ndvi / 0.8)
    
    # Potencial base (ton/ha/año)
    potencial_base = 25.0
    factor_suelo = gdf_analisis['indice_fertilidad']
    
    # Cálculo final
    gdf_analisis['potencial_cosecha'] = (
        potencial_base * 
        factor_suelo * 
        factor_rad * 
        factor_agua * 
        factor_viento * 
        factor_ndvi
    )
    
    # Añadir datos climáticos y de satélite
    for key, value in datos_clima.items():
        gdf_analisis[key] = value
    for key, value in datos_planetscope.items():
        gdf_analisis[key] = value
        
    return gdf_analisis

# ============================================================================
# RESTO DE FUNCIONES (TEXTURA, FERTILIDAD, MAPAS, ETC.)
# ============================================================================

# [Mantén todas las funciones que ya tienes: calcular_superficie, procesar_archivo, 
#  clasificar_textura_suelo, analizar_textura_suelo, dividir_parcela_en_zonas, 
#  calcular_indices_gee, crear_mapa_interactivo, crear_mapa_visualizador_parcela, 
#  crear_mapa_estatico, mostrar_recomendaciones_agroecologicas, generar_informe_pdf, 
#  mostrar_resultados_textura, mostrar_resultados_principales, mostrar_modo_demo, 
#  mostrar_configuracion_parcela]

# Por brevedad, aquí resumimos solo las partes nuevas relacionadas con PlanetScope y cosecha

def mostrar_potencial_cosecha():
    """Muestra resultados de potencial de cosecha"""
    if 'gdf_analisis' not in st.session_state or st.session_state.gdf_analisis is None:
        st.warning("No hay datos de análisis disponibles")
        return
        
    gdf = st.session_state.gdf_analisis
    clima = st.session_state.get('datos_clima', {})
    planetscope = st.session_state.get('datos_planetscope', {})
    
    st.markdown("## 🌴 POTENCIAL DE COSECHA - PALMA ACEITERA")
    
    # Resumen de datos
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("☀️ Radiación Solar", f"{clima.get('radiacion_solar', 0):.1f} MJ/m²/día")
    with col2:
        st.metric("🌧️ Precipitación", f"{clima.get('precipitacion', 0)*30:.0f} mm/mes")
    with col3:
        st.metric("💨 Viento", f"{clima.get('velocidad_viento', 0):.1f} m/s")
    with col4:
        st.metric("🛰️ NDVI (PlanetScope)", f"{planetscope.get('ndvi_planetscope', 0):.2f}")
    
    # Potencial promedio
    potencial_prom = gdf['potencial_cosecha'].mean()
    st.metric("📦 Potencial Cosecha Promedio", f"{potencial_prom:.1f} ton/ha/año")
    
    # Mapa de potencial
    st.subheader("🗺️ Mapa de Potencial de Cosecha")
    mapa_potencial = crear_mapa_interactivo(
        gdf, 
        "Potencial de Cosecha - Palma Aceitera", 
        'potencial_cosecha', 
        "POTENCIAL_COSECHA", 
        "PALMA"
    )
    st_folium(mapa_potencial, width=800, height=500)
    
    # Tabla detallada
    st.subheader("📋 Datos por Zona")
    columnas_cosecha = ['id_zona', 'potencial_cosecha', 'indice_fertilidad', 
                       'radiacion_solar', 'precipitacion_mm_mes', 'velocidad_viento', 'ndvi_planetscope']
    df_cosecha = gdf[columnas_cosecha].copy()
    df_cosecha['precipitacion_mm_mes'] = df_cosecha['precipitacion'] * 30
    st.dataframe(df_cosecha.round(2), use_container_width=True)
    
    # Recomendaciones basadas en cosecha
    st.markdown("### 📈 Recomendaciones para Maximizar Cosecha")
    if potencial_prom < 15:
        st.error("🚨 **BAJO POTENCIAL**: Considerar mejoras en riego, nutrición o manejo de sombra")
    elif potencial_prom < 20:
        st.warning("⚠️ **POTENCIAL MODERADO**: Optimizar fertilización y control de malezas")
    else:
        st.success("✅ **ALTO POTENCIAL**: Mantener prácticas actuales y monitorear continuamente")
    
    st.markdown("""
    **Factores críticos para palma aceitera:**
    - Radiación solar > 15 MJ/m²/día
    - Precipitación mensual > 150 mm
    - NDVI > 0.7 (buena cobertura vegetal)
    - Fertilidad del suelo óptima (NPK balanceado)
    """)

# ============================================================================
# INICIALIZACIÓN DE SESSION_STATE
# ============================================================================
if 'analisis_completado' not in st.session_state:
    st.session_state.analisis_completado = False
if 'gdf_original' not in st.session_state:
    st.session_state.gdf_original = None
if 'gdf_analisis' not in st.session_state:
    st.session_state.gdf_analisis = None
if 'analisis_textura' not in st.session_state:
    st.session_state.analisis_textura = None
if 'area_total' not in st.session_state:
    st.session_state.area_total = 0.0
if 'datos_demo' not in st.session_state:
    st.session_state.datos_demo = False
if 'cultivo' not in st.session_state:
    st.session_state.cultivo = "PALMA_ACEITERA"
if 'analisis_tipo' not in st.session_state:
    st.session_state.analisis_tipo = "FERTILIDAD ACTUAL"
if 'nutriente' not in st.session_state:
    st.session_state.nutriente = "NITRÓGENO"
if 'mes_analisis' not in st.session_state:
    st.session_state.mes_analisis = "ENERO"
if 'n_divisiones' not in st.session_state:
    st.session_state.n_divisiones = 24
if 'datos_clima' not in st.session_state:
    st.session_state.datos_clima = None
if 'datos_planetscope' not in st.session_state:
    st.session_state.datos_planetscope = None

# ============================================================================
# FUNCIONES AUXILIARES COMPLETAS (incluyendo las que faltaban)
# ============================================================================

def calcular_superficie(gdf):
    """Calcula superficie en hectáreas con manejo robusto de CRS"""
    try:
        if gdf is None or gdf.empty or gdf.geometry.isnull().all():
            return 0.0
        if gdf.crs and gdf.crs.is_geographic:
            try:
                gdf_proj = gdf.to_crs('EPSG:3116')
                area_m2 = gdf_proj.geometry.area
            except:
                try:
                    gdf_proj = gdf.to_crs('EPSG:3857')
                    area_m2 = gdf_proj.geometry.area
                except:
                    area_m2 = gdf.geometry.area.mean() * 111000 * 111000
        else:
            area_m2 = gdf.geometry.area
        area_ha = area_m2 / 10000
        return float(area_ha) if not np.isnan(area_ha) else 0.0
    except:
        return 0.0

def procesar_archivo(uploaded_file):
    """Procesa el archivo ZIP con shapefile o archivo KML"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            if uploaded_file.name.lower().endswith('.kml'):
                gdf = gpd.read_file(file_path, driver='KML')
            else:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                kml_files = [f for f in os.listdir(tmp_dir) if f.endswith('.kml')]
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                elif kml_files:
                    kml_path = os.path.join(tmp_dir, kml_files[0])
                    gdf = gpd.read_file(kml_path, driver='KML')
                else:
                    return None
            if not gdf.is_valid.all():
                gdf = gdf.make_valid()
            return gdf
    except:
        return None

def clasificar_textura_suelo(arena, limo, arcilla):
    try:
        total = arena + limo + arcilla
        if total == 0:
            return "NO_DETERMINADA"
        arena_norm = (arena / total) * 100
        limo_norm = (limo / total) * 100
        arcilla_norm = (arcilla / total) * 100
        if arcilla_norm >= 40:
            return "Arcilloso"
        elif arcilla_norm >= 27 and limo_norm >= 15 and limo_norm <= 53 and arena_norm >= 20 and arena_norm <= 45:
            return "Franco Arcilloso"
        elif arcilla_norm >= 7 and arcilla_norm <= 27 and limo_norm >= 28 and limo_norm <= 50 and arena_norm >= 43 and arena_norm <= 52:
            return "Franco"
        elif arena_norm >= 70 and arena_norm <= 85 and arcilla_norm <= 20:
            return "Franco Arcilloso-Arenoso"
        elif arena_norm >= 85:
            return "Arenoso"
        else:
            return "Franco"
    except:
        return "NO_DETERMINADA"

def calcular_propiedades_fisicas_suelo(textura, materia_organica):
    propiedades = {
        'capacidad_campo': 0.0,
        'punto_marchitez': 0.0,
        'agua_disponible': 0.0,
        'densidad_aparente': 0.0,
        'porosidad': 0.0,
        'conductividad_hidraulica': 0.0
    }
    base_propiedades = {
        'Arcilloso': {'cc': 350, 'pm': 200, 'da': 1.3, 'porosidad': 0.5, 'kh': 0.1},
        'Franco Arcilloso': {'cc': 300, 'pm': 150, 'da': 1.25, 'porosidad': 0.53, 'kh': 0.5},
        'Franco': {'cc': 250, 'pm': 100, 'da': 1.2, 'porosidad': 0.55, 'kh': 1.5},
        'Franco Arcilloso-Arenoso': {'cc': 180, 'pm': 80, 'da': 1.35, 'porosidad': 0.49, 'kh': 5.0},
        'Arenoso': {'cc': 120, 'pm': 50, 'da': 1.5, 'porosidad': 0.43, 'kh': 15.0}
    }
    if textura in base_propiedades:
        base = base_propiedades[textura]
        factor_mo = 1.0 + (materia_organica * 0.05)
        propiedades['capacidad_campo'] = base['cc'] * factor_mo
        propiedades['punto_marchitez'] = base['pm'] * factor_mo
        propiedades['agua_disponible'] = (base['cc'] - base['pm']) * factor_mo
        propiedades['densidad_aparente'] = base['da'] / factor_mo
        propiedades['porosidad'] = min(0.65, base['porosidad'] * factor_mo)
        propiedades['conductividad_hidraulica'] = base['kh'] * factor_mo
    return propiedades

def evaluar_adecuacion_textura(textura_actual, cultivo):
    textura_optima = TEXTURA_SUELO_OPTIMA[cultivo]['textura_optima']
    jerarquia_texturas = {
        'Arenoso': 1,
        'Franco Arcilloso-Arenoso': 2,
        'Franco': 3,
        'Franco Arcilloso': 4,
        'Arcilloso': 5
    }
    if textura_actual not in jerarquia_texturas:
        return "NO_DETERMINADA", 0
    actual_idx = jerarquia_texturas[textura_actual]
    optima_idx = jerarquia_texturas[textura_optima]
    diferencia = abs(actual_idx - optima_idx)
    if diferencia == 0:
        return "ÓPTIMA", 1.0
    elif diferencia == 1:
        return "ADECUADA", 0.8
    elif diferencia == 2:
        return "MODERADA", 0.6
    elif diferencia == 3:
        return "LIMITANTE", 0.4
    else:
        return "MUY LIMITANTE", 0.2

def analizar_textura_suelo(gdf, cultivo, mes_analisis):
    params_textura = TEXTURA_SUELO_OPTIMA[cultivo]
    zonas_gdf = gdf.copy()
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['arena'] = 0.0
    zonas_gdf['limo'] = 0.0
    zonas_gdf['arcilla'] = 0.0
    zonas_gdf['textura_suelo'] = "NO_DETERMINADA"
    zonas_gdf['adecuacion_textura'] = 0.0
    zonas_gdf['categoria_adecuacion'] = "NO_DETERMINADA"
    zonas_gdf['capacidad_campo'] = 0.0
    zonas_gdf['punto_marchitez'] = 0.0
    zonas_gdf['agua_disponible'] = 0.0
    zonas_gdf['densidad_aparente'] = 0.0
    zonas_gdf['porosidad'] = 0.0
    zonas_gdf['conductividad_hidraulica'] = 0.0
    for idx, row in zonas_gdf.iterrows():
        try:
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_textura")) % (2**32)
            rng = np.random.RandomState(seed_value)
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            variabilidad_local = 0.15 + 0.7 * (lat_norm * lon_norm)
            arena_optima = params_textura['arena_optima']
            limo_optima = params_textura['limo_optima']
            arcilla_optima = params_textura['arcilla_optima']
            arena = max(5, min(95, rng.normal(
                arena_optima * (0.8 + 0.4 * variabilidad_local),
                arena_optima * 0.2
            )))
            limo = max(5, min(95, rng.normal(
                limo_optima * (0.7 + 0.6 * variabilidad_local),
                limo_optima * 0.25
            )))
            arcilla = max(5, min(95, rng.normal(
                arcilla_optima * (0.75 + 0.5 * variabilidad_local),
                arcilla_optima * 0.3
            )))
            total = arena + limo + arcilla
            arena = (arena / total) * 100
            limo = (limo / total) * 100
            arcilla = (arcilla / total) * 100
            textura = clasificar_textura_suelo(arena, limo, arcilla)
            categoria_adecuacion, puntaje_adecuacion = evaluar_adecuacion_textura(textura, cultivo)
            materia_organica = max(1.0, min(8.0, rng.normal(3.0, 1.0)))
            propiedades_fisicas = calcular_propiedades_fisicas_suelo(textura, materia_organica)
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'arena'] = arena
            zonas_gdf.loc[idx, 'limo'] = limo
            zonas_gdf.loc[idx, 'arcilla'] = arcilla
            zonas_gdf.loc[idx, 'textura_suelo'] = textura
            zonas_gdf.loc[idx, 'adecuacion_textura'] = puntaje_adecuacion
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = categoria_adecuacion
            zonas_gdf.loc[idx, 'capacidad_campo'] = propiedades_fisicas['capacidad_campo']
            zonas_gdf.loc[idx, 'punto_marchitez'] = propiedades_fisicas['punto_marchitez']
            zonas_gdf.loc[idx, 'agua_disponible'] = propiedades_fisicas['agua_disponible']
            zonas_gdf.loc[idx, 'densidad_aparente'] = propiedades_fisicas['densidad_aparente']
            zonas_gdf.loc[idx, 'porosidad'] = propiedades_fisicas['porosidad']
            zonas_gdf.loc[idx, 'conductividad_hidraulica'] = propiedades_fisicas['conductividad_hidraulica']
        except:
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'arena'] = params_textura['arena_optima']
            zonas_gdf.loc[idx, 'limo'] = params_textura['limo_optima']
            zonas_gdf.loc[idx, 'arcilla'] = params_textura['arcilla_optima']
            zonas_gdf.loc[idx, 'textura_suelo'] = params_textura['textura_optima']
            zonas_gdf.loc[idx, 'adecuacion_textura'] = 1.0
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = "ÓPTIMA"
            propiedades_default = calcular_propiedades_fisicas_suelo(params_textura['textura_optima'], 3.0)
            for prop, valor in propiedades_default.items():
                zonas_gdf.loc[idx, prop] = valor
    return zonas_gdf

def dividir_parcela_en_zonas(gdf, n_zonas):
    try:
        if len(gdf) == 0:
            return gdf
        parcela_principal = gdf.iloc[0].geometry
        if not parcela_principal.is_valid:
            parcela_principal = parcela_principal.buffer(0)
        bounds = parcela_principal.bounds
        if len(bounds) < 4:
            return gdf
        minx, miny, maxx, maxy = bounds
        if minx >= maxx or miny >= maxy:
            return gdf
        sub_poligonos = []
        n_cols = math.ceil(math.sqrt(n_zonas))
        n_rows = math.ceil(n_zonas / n_cols)
        width = (maxx - minx) / n_cols
        height = (maxy - miny) / n_rows
        if width < 0.0001 or height < 0.0001:
            n_zonas = min(n_zonas, 16)
            n_cols = math.ceil(math.sqrt(n_zonas))
            n_rows = math.ceil(n_zonas / n_cols)
            width = (maxx - minx) / n_cols
            height = (maxy - miny) / n_rows
        for i in range(n_rows):
            for j in range(n_cols):
                if len(sub_poligonos) >= n_zonas:
                    break
                cell_minx = minx + (j * width)
                cell_maxx = minx + ((j + 1) * width)
                cell_miny = miny + (i * height)
                cell_maxy = miny + ((i + 1) * height)
                try:
                    cell_poly = Polygon([
                        (cell_minx, cell_miny),
                        (cell_maxx, cell_miny),
                        (cell_maxx, cell_maxy),
                        (cell_minx, cell_maxy)
                    ])
                    if cell_poly.is_valid:
                        intersection = parcela_principal.intersection(cell_poly)
                        if not intersection.is_empty and intersection.area > 0:
                            if intersection.geom_type == 'MultiPolygon':
                                largest = max(intersection.geoms, key=lambda p: p.area)
                                sub_poligonos.append(largest)
                            else:
                                sub_poligonos.append(intersection)
                except:
                    continue
        if sub_poligonos:
            nuevo_gdf = gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
            return nuevo_gdf
        else:
            return gdf
    except:
        return gdf

def calcular_indices_gee(gdf, cultivo, mes_analisis, analisis_tipo, nutriente):
    params = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    factor_mes = FACTORES_MES[mes_analisis]
    factor_n_mes = FACTORES_N_MES[mes_analisis]
    factor_p_mes = FACTORES_P_MES[mes_analisis]
    factor_k_mes = FACTORES_K_MES[mes_analisis]
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['nitrogeno'] = 0.0
    zonas_gdf['fosforo'] = 0.0
    zonas_gdf['potasio'] = 0.0
    zonas_gdf['materia_organica'] = 0.0
    zonas_gdf['humedad'] = 0.0
    zonas_gdf['ph'] = 0.0
    zonas_gdf['conductividad'] = 0.0
    zonas_gdf['ndvi'] = 0.0
    zonas_gdf['indice_fertilidad'] = 0.0
    zonas_gdf['categoria'] = "MEDIA"
    zonas_gdf['recomendacion_npk'] = 0.0
    zonas_gdf['deficit_npk'] = 0.0
    zonas_gdf['prioridad'] = "MEDIA"
    for idx, row in zonas_gdf.iterrows():
        try:
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}")) % (2**32)
            rng = np.random.RandomState(seed_value)
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            n_optimo = params['NITROGENO']['optimo']
            p_optimo = params['FOSFORO']['optimo']
            k_optimo = params['POTASIO']['optimo']
            variabilidad_local = 0.2 + 0.6 * (lat_norm * lon_norm)
            nitrogeno = max(0, rng.normal(
                n_optimo * (0.8 + 0.4 * variabilidad_local), 
                n_optimo * 0.15
            ))
            fosforo = max(0, rng.normal(
                p_optimo * (0.7 + 0.6 * variabilidad_local),
                p_optimo * 0.2
            ))
            potasio = max(0, rng.normal(
                k_optimo * (0.75 + 0.5 * variabilidad_local),
                k_optimo * 0.18
            ))
            nitrogeno *= factor_n_mes * (0.9 + 0.2 * rng.random())
            fosforo *= factor_p_mes * (0.9 + 0.2 * rng.random())
            potasio *= factor_k_mes * (0.9 + 0.2 * rng.random())
            materia_organica = max(1.0, min(8.0, rng.normal(
                params['MATERIA_ORGANICA_OPTIMA'], 
                1.0
            )))
            humedad = max(0.1, min(0.8, rng.normal(
                params['HUMEDAD_OPTIMA'],
                0.1
            )))
            ph = max(4.0, min(8.0, rng.normal(
                params['pH_OPTIMO'],
                0.5
            )))
            conductividad = max(0.1, min(3.0, rng.normal(
                params['CONDUCTIVIDAD_OPTIMA'],
                0.3
            )))
            base_ndvi = 0.3 + 0.5 * variabilidad_local
            ndvi = max(0.1, min(0.95, rng.normal(base_ndvi, 0.1)))
            n_norm = max(0, min(1, nitrogeno / (n_optimo * 1.5)))
            p_norm = max(0, min(1, fosforo / (p_optimo * 1.5)))
            k_norm = max(0, min(1, potasio / (k_optimo * 1.5)))
            mo_norm = max(0, min(1, materia_organica / 8.0))
            ph_norm = max(0, min(1, 1 - abs(ph - params['pH_OPTIMO']) / 2.0))
            indice_fertilidad = (
                n_norm * 0.25 + 
                p_norm * 0.20 + 
                k_norm * 0.20 + 
                mo_norm * 0.15 +
                ph_norm * 0.10 +
                ndvi * 0.10
            ) * factor_mes
            indice_fertilidad = max(0, min(1, indice_fertilidad))
            if indice_fertilidad >= 0.85:
                categoria = "EXCELENTE"
                prioridad = "BAJA"
            elif indice_fertilidad >= 0.70:
                categoria = "MUY ALTA"
                prioridad = "MEDIA-BAJA"
            elif indice_fertilidad >= 0.55:
                categoria = "ALTA"
                prioridad = "MEDIA"
            elif indice_fertilidad >= 0.40:
                categoria = "MEDIA"
                prioridad = "MEDIA-ALTA"
            elif indice_fertilidad >= 0.25:
                categoria = "BAJA"
                prioridad = "ALTA"
            else:
                categoria = "MUY BAJA"
                prioridad = "URGENTE"
            if analisis_tipo == "RECOMENDACIONES NPK":
                if nutriente == "NITRÓGENO":
                    deficit_nitrogeno = max(0, n_optimo - nitrogeno)
                    factor_eficiencia = 1.4
                    factor_crecimiento = 1.2
                    factor_materia_organica = max(0.7, 1.0 - (materia_organica / 15.0))
                    factor_ndvi = 1.0 + (0.5 - ndvi) * 0.4
                    recomendacion = (deficit_nitrogeno * factor_eficiencia * factor_crecimiento * 
                                   factor_materia_organica * factor_ndvi)
                    recomendacion = min(recomendacion, 250)
                    recomendacion = max(20, recomendacion)
                    deficit = deficit_nitrogeno
                elif nutriente == "FÓSFORO":
                    deficit_fosforo = max(0, p_optimo - fosforo)
                    factor_eficiencia = 1.6
                    factor_ph = 1.0
                    if ph < 5.5 or ph > 7.5:
                        factor_ph = 1.3
                    factor_materia_organica = 1.1
                    recomendacion = (deficit_fosforo * factor_eficiencia * 
                                   factor_ph * factor_materia_organica)
                    recomendacion = min(recomendacion, 120)
                    recomendacion = max(10, recomendacion)
                    deficit = deficit_fosforo
                else:
                    deficit_potasio = max(0, k_optimo - potasio)
                    factor_eficiencia = 1.3
                    factor_textura = 1.0
                    if materia_organica < 2.0:
                        factor_textura = 1.2
                    factor_rendimiento = 1.0 + (0.5 - ndvi) * 0.3
                    recomendacion = (deficit_potasio * factor_eficiencia * 
                                   factor_textura * factor_rendimiento)
                    recomendacion = min(recomendacion, 200)
                    recomendacion = max(15, recomendacion)
                    deficit = deficit_potasio
                if categoria in ["MUY BAJA", "BAJA"]:
                    recomendacion *= 1.3
                elif categoria in ["ALTA", "MUY ALTA", "EXCELENTE"]:
                    recomendacion *= 0.8
            else:
                recomendacion = 0
                deficit = 0
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'nitrogeno'] = nitrogeno
            zonas_gdf.loc[idx, 'fosforo'] = fosforo
            zonas_gdf.loc[idx, 'potasio'] = potasio
            zonas_gdf.loc[idx, 'materia_organica'] = materia_organica
            zonas_gdf.loc[idx, 'humedad'] = humedad
            zonas_gdf.loc[idx, 'ph'] = ph
            zonas_gdf.loc[idx, 'conductividad'] = conductividad
            zonas_gdf.loc[idx, 'ndvi'] = ndvi
            zonas_gdf.loc[idx, 'indice_fertilidad'] = indice_fertilidad
            zonas_gdf.loc[idx, 'categoria'] = categoria
            zonas_gdf.loc[idx, 'recomendacion_npk'] = recomendacion
            zonas_gdf.loc[idx, 'deficit_npk'] = deficit
            zonas_gdf.loc[idx, 'prioridad'] = prioridad
        except:
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'nitrogeno'] = params['NITROGENO']['optimo'] * 0.8
            zonas_gdf.loc[idx, 'fosforo'] = params['FOSFORO']['optimo'] * 0.8
            zonas_gdf.loc[idx, 'potasio'] = params['POTASIO']['optimo'] * 0.8
            zonas_gdf.loc[idx, 'materia_organica'] = params['MATERIA_ORGANICA_OPTIMA']
            zonas_gdf.loc[idx, 'humedad'] = params['HUMEDAD_OPTIMA']
            zonas_gdf.loc[idx, 'ph'] = params['pH_OPTIMO']
            zonas_gdf.loc[idx, 'conductividad'] = params['CONDUCTIVIDAD_OPTIMA']
            zonas_gdf.loc[idx, 'ndvi'] = 0.6
            zonas_gdf.loc[idx, 'indice_fertilidad'] = 0.5
            zonas_gdf.loc[idx, 'categoria'] = "MEDIA"
            zonas_gdf.loc[idx, 'recomendacion_npk'] = 0
            zonas_gdf.loc[idx, 'deficit_npk'] = 0
            zonas_gdf.loc[idx, 'prioridad'] = "MEDIA"
    return zonas_gdf

# PARÁMETROS DE TEXTURA DEL SUELO
TEXTURA_SUELO_OPTIMA = {
    'PALMA_ACEITERA': {
        'textura_optima': 'Franco Arcilloso',
        'arena_optima': 40,
        'limo_optima': 30,
        'arcilla_optima': 30,
        'densidad_aparente_optima': 1.3,
        'porosidad_optima': 0.5
    },
    'CACAO': {
        'textura_optima': 'Franco',
        'arena_optima': 45,
        'limo_optima': 35,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.2,
        'porosidad_optima': 0.55
    },
    'BANANO': {
        'textura_optima': 'Franco Arcilloso-Arenoso',
        'arena_optima': 50,
        'limo_optima': 30,
        'arcilla_optima': 20,
        'densidad_aparente_optima': 1.25,
        'porosidad_optima': 0.52
    }
}

# FACTORES ESTACIONALES
FACTORES_MES = {
    "ENERO": 0.9, "FEBRERO": 0.95, "MARZO": 1.0, "ABRIL": 1.05,
    "MAYO": 1.1, "JUNIO": 1.0, "JULIO": 0.95, "AGOSTO": 0.9,
    "SEPTIEMBRE": 0.95, "OCTUBRE": 1.0, "NOVIEMBRE": 1.05, "DICIEMBRE": 1.0
}
FACTORES_N_MES = {
    "ENERO": 1.0, "FEBRERO": 1.05, "MARZO": 1.1, "ABRIL": 1.15,
    "MAYO": 1.2, "JUNIO": 1.1, "JULIO": 1.0, "AGOSTO": 0.9,
    "SEPTIEMBRE": 0.95, "OCTUBRE": 1.0, "NOVIEMBRE": 1.05, "DICIEMBRE": 1.0
}
FACTORES_P_MES = {
    "ENERO": 1.0, "FEBRERO": 1.0, "MARZO": 1.05, "ABRIL": 1.1,
    "MAYO": 1.15, "JUNIO": 1.1, "JULIO": 1.05, "AGOSTO": 1.0,
    "SEPTIEMBRE": 1.0, "OCTUBRE": 1.05, "NOVIEMBRE": 1.1, "DICIEMBRE": 1.05
}
FACTORES_K_MES = {
    "ENERO": 1.0, "FEBRERO": 1.0, "MARZO": 1.0, "ABRIL": 1.05,
    "MAYO": 1.1, "JUNIO": 1.15, "JULIO": 1.2, "AGOSTO": 1.15,
    "SEPTIEMBRE": 1.1, "OCTUBRE": 1.05, "NOVIEMBRE": 1.0, "DICIEMBRE": 1.0
}

# PALETAS
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
    'FOSFORO': ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
    'POTASIO': ['#4d004b', '#810f7c', '#8c6bb1', '#8c96c6', '#9ebcda', '#bfd3e6', '#e0ecf4', '#edf8fb'],
    'TEXTURA': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'],
    'POTENCIAL': ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b']
}

# ============================================================================
# FUNCIONES DE VISUALIZACIÓN ACTUALIZADAS
# ============================================================================

def crear_mapa_interactivo(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=15,
        tiles='OpenStreetMap',
        attr='© OpenStreetMap contributors',
        name='OpenStreetMap'
    )
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite',
        overlay=False
    ).add_to(m)
    folium.LayerControl().add_to(m)
    
    if columna_valor and analisis_tipo:
        if analisis_tipo == "FERTILIDAD ACTUAL":
            vmin, vmax = 0, 1
            colores = PALETAS_GEE['FERTILIDAD']
            unidad = "Índice"
        elif analisis_tipo == "ANÁLISIS DE TEXTURA":
            colores_textura = {
                'Arenoso': '#d8b365',
                'Franco Arcilloso-Arenoso': '#f6e8c3', 
                'Franco': '#c7eae5',
                'Franco Arcilloso': '#5ab4ac',
                'Arcilloso': '#01665e',
                'NO_DETERMINADA': '#999999'
            }
            unidad = "Textura"
        elif analisis_tipo == "POTENCIAL_COSECHA":
            vmin, vmax = 0, 30
            colores = PALETAS_GEE['POTENCIAL']
            unidad = "ton/ha/año"
        else:
            if nutriente == "NITRÓGENO":
                vmin, vmax = 0, 250
                colores = PALETAS_GEE['NITROGENO']
                unidad = "kg/ha N"
            elif nutriente == "FÓSFORO":
                vmin, vmax = 0, 120
                colores = PALETAS_GEE['FOSFORO']
                unidad = "kg/ha P₂O₅"
            else:
                vmin, vmax = 0, 200
                colores = PALETAS_GEE['POTASIO']
                unidad = "kg/ha K₂O"
                
        def obtener_color(valor, vmin, vmax, colores):
            if vmax == vmin:
                return colores[len(colores)//2]
            valor_norm = (valor - vmin) / (vmax - vmin)
            valor_norm = max(0, min(1, valor_norm))
            idx = int(valor_norm * (len(colores) - 1))
            return colores[idx]
            
        for idx, row in gdf.iterrows():
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                textura = row[columna_valor]
                color = colores_textura.get(textura, '#999999')
                valor_display = textura
            else:
                valor = row[columna_valor]
                color = obtener_color(valor, vmin, vmax, colores)
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    valor_display = f"{valor:.3f}"
                elif analisis_tipo == "POTENCIAL_COSECHA":
                    valor_display = f"{valor:.1f}"
                else:
                    valor_display = f"{valor:.1f}"
                    
            # Popup según tipo
            if analisis_tipo == "POTENCIAL_COSECHA":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Potencial Cosecha:</b> {valor_display} {unidad}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <hr>
                    <b>Radiación:</b> {row.get('radiacion_solar', 0):.1f} MJ/m²/día<br>
                    <b>Precipitación:</b> {row.get('precipitacion', 0)*30:.0f} mm/mes<br>
                    <b>Viento:</b> {row.get('velocidad_viento', 0):.1f} m/s<br>
                    <b>NDVI:</b> {row.get('ndvi_planetscope', 0):.2f}
                </div>
                """
            elif analisis_tipo == "FERTILIDAD ACTUAL":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Índice Fertilidad:</b> {valor_display}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <b>Categoría:</b> {row.get('categoria', 'N/A')}<br>
                    <b>Prioridad:</b> {row.get('prioridad', 'N/A')}<br>
                    <hr>
                    <b>N:</b> {row.get('nitrogeno', 0):.1f} kg/ha<br>
                    <b>P:</b> {row.get('fosforo', 0):.1f} kg/ha<br>
                    <b>K:</b> {row.get('potasio', 0):.1f} kg/ha<br>
                    <b>MO:</b> {row.get('materia_organica', 0):.1f}%<br>
                    <b>NDVI:</b> {row.get('ndvi', 0):.3f}
                </div>
                """
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Textura:</b> {valor_display}<br>
                    <b>Adecuación:</b> {row.get('adecuacion_textura', 0):.1%}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <hr>
                    <b>Arena:</b> {row.get('arena', 0):.1f}%<br>
                    <b>Limo:</b> {row.get('limo', 0):.1f}%<br>
                    <b>Arcilla:</b> {row.get('arcilla', 0):.1f}%<br>
                    <b>Capacidad Campo:</b> {row.get('capacidad_campo', 0):.1f} mm/m<br>
                    <b>Agua Disponible:</b> {row.get('agua_disponible', 0):.1f} mm/m
                </div>
                """
            else:
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Recomendación {nutriente}:</b> {valor_display} {unidad}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <b>Categoría Fertilidad:</b> {row.get('categoria', 'N/A')}<br>
                    <b>Prioridad:</b> {row.get('prioridad', 'N/A')}<br>
                    <hr>
                    <b>N Actual:</b> {row.get('nitrogeno', 0):.1f} kg/ha<br>
                    <b>P Actual:</b> {row.get('fosforo', 0):.1f} kg/ha<br>
                    <b>K Actual:</b> {row.get('potasio', 0):.1f} kg/ha<br>
                    <b>Déficit:</b> {row.get('deficit_npk', 0):.1f} kg/ha
                </div>
                """
                
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.7,
                    'opacity': 0.9
                },
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"Zona {row['id_zona']}: {valor_display}"
            ).add_to(m)
            
            centroid = row.geometry.centroid
            folium.Marker(
                [centroid.y, centroid.x],
                icon=folium.DivIcon(
                    html=f'''
                    <div style="
                        background-color: white; 
                        border: 2px solid black; 
                        border-radius: 50%; 
                        width: 28px; 
                        height: 28px; 
                        display: flex; 
                        align-items: center; 
                        justify-content: center; 
                        font-weight: bold; 
                        font-size: 11px;
                        color: black;
                    ">{row["id_zona"]}</div>
                    '''
                ),
                tooltip=f"Zona {row['id_zona']} - Click para detalles"
            ).add_to(m)
    else:
        for idx, row in gdf.iterrows():
            area_ha = calcular_superficie(gdf.iloc[[idx]])
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x: {
                    'fillColor': '#1f77b4',
                    'color': '#2ca02c',
                    'weight': 3,
                    'fillOpacity': 0.5,
                    'opacity': 0.8
                },
                popup=folium.Popup(
                    f"<b>Polígono {idx + 1}</b><br>Área: {area_ha:.2f} ha", 
                    max_width=300
                ),
            ).add_to(m)
            
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    return m

def crear_mapa_visualizador_parcela(gdf):
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=14,
        tiles='OpenStreetMap',
        attr='© OpenStreetMap contributors',
        name='OpenStreetMap'
    )
    for idx, row in gdf.iterrows():
        area_ha = calcular_superficie(gdf.iloc[[idx]])
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda x: {
                'fillColor': '#1f77b4',
                'color': '#2ca02c',
                'weight': 3,
                'fillOpacity': 0.4,
                'opacity': 0.8
            },
            popup=folium.Popup(
                f"<b>Parcela {idx + 1}</b><br>"
                f"<b>Área:</b> {area_ha:.2f} ha<br>"
                f"<b>Coordenadas:</b> {centroid.y:.4f}, {centroid.x:.4f}",
                max_width=300
            ),
            tooltip=f"Parcela {idx + 1} - {area_ha:.2f} ha"
        ).add_to(m)
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    folium.LayerControl().add_to(m)
    return m

def crear_mapa_estatico(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        if columna_valor and analisis_tipo:
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
                vmin, vmax = 0, 1
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                colores_textura = {
                    'Arenoso': '#d8b365',
                    'Franco Arcilloso-Arenoso': '#f6e8c3', 
                    'Franco': '#c7eae5',
                    'Franco Arcilloso': '#5ab4ac',
                    'Arcilloso': '#01665e',
                    'NO_DETERMINADA': '#999999'
                }
            elif analisis_tipo == "POTENCIAL_COSECHA":
                cmap = LinearSegmentedColormap.from_list('potencial_gee', PALETAS_GEE['POTENCIAL'])
                vmin, vmax = 0, 30
            else:
                if nutriente == "NITRÓGENO":
                    cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
                    vmin, vmax = 0, 250
                elif nutriente == "FÓSFORO":
                    cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
                    vmin, vmax = 0, 120
                else:
                    cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
                    vmin, vmax = 0, 200
                    
            for idx, row in gdf.iterrows():
                if analisis_tipo == "ANÁLISIS DE TEXTURA":
                    textura = row[columna_valor]
                    color = colores_textura.get(textura, '#999999')
                else:
                    valor = row[columna_valor]
                    valor_norm = (valor - vmin) / (vmax - vmin)
                    valor_norm = max(0, min(1, valor_norm))
                    color = cmap(valor_norm)
                gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1)
                centroid = row.geometry.centroid
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    texto_valor = f"{row[columna_valor]:.3f}"
                elif analisis_tipo == "POTENCIAL_COSECHA":
                    texto_valor = f"{row[columna_valor]:.1f}"
                else:
                    texto_valor = f"{row[columna_valor]:.0f} kg"
                ax.annotate(f"Z{row['id_zona']}\n{texto_valor}", 
                           (centroid.x, centroid.y), 
                           xytext=(3, 3), textcoords="offset points", 
                           fontsize=6, color='black', weight='bold',
                           bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8),
                           ha='center', va='center')
        else:
            gdf.plot(ax=ax, color='lightblue', edgecolor='black', linewidth=2, alpha=0.7)
        ax.set_title(f'🗺️ {titulo}', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        if columna_valor and analisis_tipo and analisis_tipo != "ANÁLISIS DE TEXTURA":
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cbar.set_label('Índice NPK Actual (0-1)', fontsize=10)
                cbar.set_ticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
                cbar.set_ticklabels(['0.0 (Muy Baja)', '0.2', '0.4 (Media)', '0.6', '0.8', '1.0 (Muy Alta)'])
            elif analisis_tipo == "POTENCIAL_COSECHA":
                cbar.set_label('Potencial de Cosecha (ton/ha/año)', fontsize=10)
                cbar.set_ticks([0, 5, 10, 15, 20, 25, 30])
            else:
                cbar.set_label(f'Recomendación {nutriente} (kg/ha)', fontsize=10)
                if nutriente == "NITRÓGENO":
                    cbar.set_ticks([0, 50, 100, 150, 200, 250])
                    cbar.set_ticklabels(['0', '50', '100', '150', '200', '250 kg/ha'])
                elif nutriente == "FÓSFORO":
                    cbar.set_ticks([0, 24, 48, 72, 96, 120])
                    cbar.set_ticklabels(['0', '24', '48', '72', '96', '120 kg/ha'])
                else:
                    cbar.set_ticks([0, 40, 80, 120, 160, 200])
                    cbar.set_ticklabels(['0', '40', '80', '120', '160', '200 kg/ha'])
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        st.error(f"Error creando mapa estático: {str(e)}")
        return None

# ============================================================================
# FUNCIONES DE RECOMENDACIONES Y DEMÁS (resumidas por brevedad)
# ============================================================================

RECOMENDACIONES_TEXTURA = {
    'Arcilloso': [
        "Añadir materia orgánica para mejorar estructura",
        "Evitar laboreo en condiciones húmedas",
        "Implementar drenajes superficiales",
        "Usar cultivos de cobertura para romper compactación"
    ],
    'Franco Arcilloso': [
        "Mantener niveles adecuados de materia orgánica",
        "Rotación de cultivos para mantener estructura",
        "Laboreo mínimo conservacionista",
        "Aplicación moderada de enmiendas"
    ],
    'Franco': [
        "Textura ideal - mantener prácticas conservacionistas",
        "Rotación balanceada de cultivos",
        "Manejo integrado de nutrientes",
        "Conservar estructura con coberturas"
    ],
    'Franco Arcilloso-Arenoso': [
        "Aplicación frecuente de materia orgánica",
        "Riego por goteo para eficiencia hídrica",
        "Fertilización fraccionada para reducir pérdidas",
        "Cultivos de cobertura para retener humedad"
    ],
    'Arenoso': [
        "Altas dosis de materia orgánica y compost",
        "Sistema de riego por goteo con alta frecuencia",
        "Fertilización en múltiples aplicaciones",
        "Barreras vivas para reducir erosión"
    ]
}

RECOMENDACIONES_AGROECOLOGICAS = {
    'PALMA_ACEITERA': {
        'COBERTURAS_VIVAS': [
            "Leguminosas: Centrosema pubescens, Pueraria phaseoloides",
            "Coberturas mixtas: Maní forrajero (Arachis pintoi)",
            "Plantas de cobertura baja: Dichondra repens"
        ],
        'ABONOS_VERDES': [
            "Crotalaria juncea: 3-4 kg/ha antes de la siembra",
            "Mucuna pruriens: 2-3 kg/ha para control de malezas",
            "Canavalia ensiformis: Fijación de nitrógeno"
        ],
        'BIOFERTILIZANTES': [
            "Bocashi: 2-3 ton/ha cada 6 meses",
            "Compost de racimo vacío: 1-2 ton/ha",
            "Biofertilizante líquido: Aplicación foliar mensual"
        ],
        'MANEJO_ECOLOGICO': [
            "Uso de trampas amarillas para insectos",
            "Cultivos trampa: Maíz alrededor de la plantación",
            "Conservación de enemigos naturales"
        ],
        'ASOCIACIONES': [
            "Piña en calles durante primeros 2 años",
            "Yuca en calles durante establecimiento",
            "Leguminosas arbustivas como cercas vivas"
        ]
    },
    'CACAO': {
        'COBERTURAS_VIVAS': [
            "Leguminosas rastreras: Arachis pintoi",
            "Coberturas sombreadas: Erythrina poeppigiana",
            "Plantas aromáticas: Lippia alba para control plagas"
        ],
        'ABONOS_VERDES': [
            "Frijol terciopelo (Mucuna pruriens): 3 kg/ha",
            "Guandul (Cajanus cajan): Podas periódicas",
            "Crotalaria: Control de nematodos"
        ],
        'BIOFERTILIZANTES': [
            "Compost de cacaoteca: 3-4 ton/ha",
            "Bocashi especial cacao: 2 ton/ha",
            "Té de compost aplicado al suelo"
        ],
        'MANEJO_ECOLOGICO': [
            "Sistema agroforestal multiestrato",
            "Manejo de sombra regulada (30-50%)",
            "Control biológico con hongos entomopatógenos"
        ],
        'ASOCIACIONES': [
            "Árboles maderables: Cedro, Caoba",
            "Frutales: Cítricos, Aguacate",
            "Plantas medicinales: Jengibre, Cúrcuma"
        ]
    },
    'BANANO': {
        'COBERTURAS_VIVAS': [
            "Arachis pintoi entre calles",
            "Leguminosas de porte bajo",
            "Coberturas para control de malas hierbas"
        ],
        'ABONOS_VERDES': [
            "Mucuna pruriens: 4 kg/ha entre ciclos",
            "Canavalia ensiformis: Fijación de N",
            "Crotalaria spectabilis: Control nematodos"
        ],
        'BIOFERTILIZANTES': [
            "Compost de pseudotallo: 4-5 ton/ha",
            "Bocashi bananero: 3 ton/ha",
            "Biofertilizante a base de micorrizas"
        ],
        'MANEJO_ECOLOGICO': [
            "Trampas cromáticas para picudos",
            "Barreras vivas con citronela",
            "Uso de trichoderma para control enfermedades"
        ],
        'ASOCIACIONES': [
            "Leguminosas arbustivas en linderos",
            "Cítricos como cortavientos",
            "Plantas repelentes: Albahaca, Menta"
        ]
    }
}

def mostrar_recomendaciones_agroecologicas(cultivo, categoria, area_ha, analisis_tipo, nutriente=None, textura_data=None):
    st.markdown("### 🌿 RECOMENDACIONES AGROECOLÓGICAS")
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and textura_
        adecuacion_promedio = textura_data.get('adecuacion_promedio', 0.5)
        textura_predominante = textura_data.get('textura_predominante', 'Franco')
        if adecuacion_promedio >= 0.8:
            enfoque = "✅ **ENFOQUE: MANTENIMIENTO**"
            intensidad = "Textura adecuada - prácticas conservacionistas"
        elif adecuacion_promedio >= 0.6:
            enfoque = "⚠️ **ENFOQUE: MEJORA MODERADA**"
            intensidad = "Ajustes menores necesarios en manejo"
        else:
            enfoque = "🚨 **ENFOQUE: MEJORA INTEGRAL**"
            intensidad = "Enmiendas y correcciones requeridas"
        st.success(f"{enfoque} - {intensidad}")
        st.markdown("#### 🏗️ Recomendaciones Específicas para Textura del Suelo")
        recomendaciones_textura = RECOMENDACIONES_TEXTURA.get(textura_predominante, [])
        for rec in recomendaciones_textura:
            st.markdown(f"• {rec}")
    else:
        if categoria in ["MUY BAJA", "BAJA"]:
            enfoque = "🚨 **ENFOQUE: RECUPERACIÓN Y REGENERACIÓN**"
            intensidad = "Alta"
        elif categoria in ["MEDIA"]:
            enfoque = "✅ **ENFOQUE: MANTENIMIENTO Y MEJORA**"
            intensidad = "Media"
        else:
            enfoque = "🌟 **ENFOQUE: CONSERVACIÓN Y OPTIMIZACIÓN**"
            intensidad = "Baja"
        st.success(f"{enfoque} - Intensidad: {intensidad}")
    recomendaciones = RECOMENDACIONES_AGROECOLOGICAS.get(cultivo, {})
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("🌱 **COBERTURAS VIVAS**", expanded=True):
            for rec in recomendaciones.get('COBERTURAS_VIVAS', []):
                st.markdown(f"• {rec}")
            if area_ha > 10:
                st.info("**Para áreas grandes:** Implementar en franjas progresivas")
            else:
                st.info("**Para áreas pequeñas:** Cobertura total recomendada")
    with col2:
        with st.expander("🌿 **ABONOS VERDES**", expanded=True):
            for rec in recomendaciones.get('ABONOS_VERDES', []):
                st.markdown(f"• {rec}")
            if intensidad == "Alta":
                st.warning("**Prioridad alta:** Sembrar inmediatamente después de análisis")
    col3, col4 = st.columns(2)
    with col3:
        with st.expander("💩 **BIOFERTILIZANTES**", expanded=True):
            for rec in recomendaciones.get('BIOFERTILIZANTES', []):
                st.markdown(f"• {rec}")
            if analisis_tipo == "RECOMENDACIONES NPK" and nutriente:
                if nutriente == "NITRÓGENO":
                    st.markdown("• **Enmienda nitrogenada:** Compost de leguminosas")
                elif nutriente == "FÓSFORO":
                    st.markdown("• **Enmienda fosfatada:** Rocas fosfóricas molidas")
                else:
                    st.markdown("• **Enmienda potásica:** Cenizas de biomasa")
    with col4:
        with st.expander("🐞 **MANEJO ECOLÓGICO**", expanded=True):
            for rec in recomendaciones.get('MANEJO_ECOLOGICO', []):
                st.markdown(f"• {rec}")
            if categoria in ["MUY BAJA", "BAJA"]:
                st.markdown("• **Urgente:** Implementar control biológico intensivo")
    with st.expander("🌳 **ASOCIACIONES Y DIVERSIFICACIÓN**", expanded=True):
        for rec in recomendaciones.get('ASOCIACIONES', []):
            st.markdown(f"• {rec}")
        st.markdown("""
        **Beneficios agroecológicos:**
        • Mejora la biodiversidad funcional
        • Reduce incidencia de plagas y enfermedades
        • Optimiza el uso de recursos (agua, luz, nutrientes)
        • Incrementa la resiliencia del sistema
        """)

# [Las funciones generar_informe_pdf, mostrar_resultados_textura, mostrar_resultados_principales, 
#  mostrar_modo_demo, mostrar_configuracion_parcela se mantienen igual - omitidas por brevedad]

def generar_informe_pdf(gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total, gdf_textura=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkgreen,
        spaceAfter=30,
        alignment=1
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.darkblue,
        spaceAfter=12,
        spaceBefore=12
    )
    normal_style = styles['Normal']
    story = []
    story.append(Paragraph("INFORME DE ANÁLISIS AGRÍCOLA", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("INFORMACIÓN GENERAL", heading_style))
    info_data = [
        ["Cultivo:", cultivo.replace('_', ' ').title()],
        ["Tipo de Análisis:", analisis_tipo],
        ["Mes de Análisis:", mes_analisis],
        ["Área Total:", f"{area_total:.2f} ha"],
        ["Fecha de Generación:", datetime.now().strftime("%d/%m/%Y %H:%M")]
    ]
    if analisis_tipo == "RECOMENDACIONES NPK":
        info_data.insert(2, ["Nutriente Analizado:", nutriente])
    info_table = Table(info_data, colWidths=[2*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    story.append(Paragraph("ESTADÍSTICAS DEL ANÁLISIS", heading_style))
    if analisis_tipo == "FERTILIDAD ACTUAL":
        stats_data = [
            ["Estadística", "Valor"],
            ["Índice Fertilidad Promedio", f"{gdf_analisis['indice_fertilidad'].mean():.3f}"],
            ["Nitrógeno Promedio (kg/ha)", f"{gdf_analisis['nitrogeno'].mean():.1f}"],
            ["Fósforo Promedio (kg/ha)", f"{gdf_analisis['fosforo'].mean():.1f}"],
            ["Potasio Promedio (kg/ha)", f"{gdf_analisis['potasio'].mean():.1f}"],
            ["Materia Orgánica Promedio (%)", f"{gdf_analisis['materia_organica'].mean():.1f}"],
            ["NDVI Promedio", f"{gdf_analisis['ndvi'].mean():.3f}"]
        ]
    elif analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        stats_data = [
            ["Estadística", "Valor"],
            ["Textura Predominante", gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "N/A"],
            ["Adecuación Promedio", f"{gdf_textura['adecuacion_textura'].mean():.1%}"],
            ["Arena Promedio (%)", f"{gdf_textura['arena'].mean():.1f}"],
            ["Limo Promedio (%)", f"{gdf_textura['limo'].mean():.1f}"],
            ["Arcilla Promedio (%)", f"{gdf_textura['arcilla'].mean():.1f}"],
            ["Agua Disponible Promedio (mm/m)", f"{gdf_textura['agua_disponible'].mean():.0f}"]
        ]
    elif analisis_tipo == "POTENCIAL_COSECHA":
        stats_data = [
            ["Estadística", "Valor"],
            ["Potencial Cosecha Promedio", f"{gdf_analisis['potencial_cosecha'].mean():.1f} ton/ha/año"],
            ["Radiación Solar Promedio", f"{gdf_analisis['radiacion_solar'].mean():.1f} MJ/m²/día"],
            ["Precipitación Promedio", f"{gdf_analisis['precipitacion'].mean()*30:.0f} mm/mes"],
            ["Velocidad Viento Promedio", f"{gdf_analisis['velocidad_viento'].mean():.1f} m/s"],
            ["NDVI Promedio (PlanetScope)", f"{gdf_analisis['ndvi_planetscope'].mean():.2f}"]
        ]
    else:
        avg_rec = gdf_analisis['recomendacion_npk'].mean()
        total_rec = (gdf_analisis['recomendacion_npk'] * gdf_analisis['area_ha']).sum()
        stats_data = [
            ["Estadística", "Valor"],
            [f"Recomendación {nutriente} Promedio (kg/ha)", f"{avg_rec:.1f}"],
            [f"Total {nutriente} Requerido (kg)", f"{total_rec:.1f}"],
            ["Nitrógeno Promedio (kg/ha)", f"{gdf_analisis['nitrogeno'].mean():.1f}"],
            ["Fósforo Promedio (kg/ha)", f"{gdf_analisis['fosforo'].mean():.1f}"],
            ["Potasio Promedio (kg/ha)", f"{gdf_analisis['potasio'].mean():.1f}"]
        ]
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 20))
    if analisis_tipo == "FERTILIDAD ACTUAL":
        story.append(Paragraph("DISTRIBUCIÓN DE CATEGORÍAS DE FERTILIDAD", heading_style))
        cat_dist = gdf_analisis['categoria'].value_counts()
        cat_data = [["Categoría", "Número de Zonas", "Porcentaje"]]
        total_zonas = len(gdf_analisis)
        for categoria, count in cat_dist.items():
            porcentaje = (count / total_zonas) * 100
            cat_data.append([categoria, str(count), f"{porcentaje:.1f}%"])
        cat_table = Table(cat_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 20))
    story.append(PageBreak())
    story.append(Paragraph("MAPA DE ANÁLISIS", heading_style))
    if analisis_tipo == "FERTILIDAD ACTUAL":
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'indice_fertilidad'
    elif analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        titulo_mapa = f"Textura del Suelo - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'textura_suelo'
        gdf_analisis = gdf_textura
    elif analisis_tipo == "POTENCIAL_COSECHA":
        titulo_mapa = f"Potencial de Cosecha - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'potencial_cosecha'
    else:
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'recomendacion_npk'
    mapa_buffer = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    if mapa_buffer:
        try:
            mapa_buffer.seek(0)
            img = Image(mapa_buffer, width=6*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"Figura 1: {titulo_mapa}", normal_style))
        except Exception as e:
            story.append(Paragraph("Error al generar el mapa para el PDF", normal_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("RESULTADOS POR ZONA (PRIMERAS 10 ZONAS)", heading_style))
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        columnas_tabla = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']
        df_tabla = gdf_textura[columnas_tabla].head(10).copy()
    elif analisis_tipo == "POTENCIAL_COSECHA":
        columnas_tabla = ['id_zona', 'area_ha', 'potencial_cosecha', 'radiacion_solar', 'precipitacion', 'velocidad_viento', 'ndvi_planetscope']
        df_tabla = gdf_analisis[columnas_tabla].head(10).copy()
    else:
        columnas_tabla = ['id_zona', 'area_ha', 'categoria', 'prioridad']
        if analisis_tipo == "FERTILIDAD ACTUAL":
            columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'materia_organica'])
        else:
            columnas_tabla.extend(['recomendacion_npk', 'deficit_npk', 'nitrogeno', 'fosforo', 'potasio'])
        df_tabla = gdf_analisis[columnas_tabla].head(10).copy()
    df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
    elif analisis_tipo == "ANÁLISIS DE TEXTURA":
        df_tabla['adecuacion_textura'] = df_tabla['adecuacion_textura'].round(3)
        df_tabla['arena'] = df_tabla['arena'].round(1)
        df_tabla['limo'] = df_tabla['limo'].round(1)
        df_tabla['arcilla'] = df_tabla['arcilla'].round(1)
    elif analisis_tipo == "POTENCIAL_COSECHA":
        df_tabla['potencial_cosecha'] = df_tabla['potencial_cosecha'].round(1)
        df_tabla['radiacion_solar'] = df_tabla['radiacion_solar'].round(1)
        df_tabla['precipitacion'] = (df_tabla['precipitacion'] * 30).round(0)
        df_tabla['velocidad_viento'] = df_tabla['velocidad_viento'].round(1)
        df_tabla['ndvi_planetscope'] = df_tabla['ndvi_planetscope'].round(2)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
        df_tabla['deficit_npk'] = df_tabla['deficit_npk'].round(1)
    if 'nitrogeno' in df_tabla.columns:
        df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
    if 'fosforo' in df_tabla.columns:
        df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
    if 'potasio' in df_tabla.columns:
        df_tabla['potasio'] = df_tabla['potasio'].round(1)
    if 'materia_organica' in df_tabla.columns:
        df_tabla['materia_organica'] = df_tabla['materia_organica'].round(1)
    table_data = [df_tabla.columns.tolist()]
    for _, row in df_tabla.iterrows():
        table_data.append(row.tolist())
    zona_table = Table(table_data, colWidths=[0.5*inch] + [0.7*inch] * (len(columnas_tabla)-1))
    zona_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    story.append(zona_table)
    if len(gdf_analisis) > 10:
        story.append(Spacer(1, 5))
        story.append(Paragraph(f"* Mostrando 10 de {len(gdf_analisis)} zonas totales. Consulte el archivo CSV para todos los datos.", 
                             ParagraphStyle('Small', parent=normal_style, fontSize=8)))
    story.append(Spacer(1, 20))
    story.append(PageBreak())
    story.append(Paragraph("RECOMENDACIONES AGROECOLÓGICAS", heading_style))
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "Franco"
        adecuacion_promedio = gdf_textura['adecuacion_textura'].mean()
        if adecuacion_promedio >= 0.8:
            enfoque = "ENFOQUE: MANTENIMIENTO - Textura adecuada"
        elif adecuacion_promedio >= 0.6:
            enfoque = "ENFOQUE: MEJORA MODERADA - Ajustes menores necesarios"
        else:
            enfoque = "ENFOQUE: MEJORA INTEGRAL - Enmiendas requeridas"
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        recomendaciones_textura = RECOMENDACIONES_TEXTURA.get(textura_predominante, [])
        story.append(Paragraph(f"<b>Recomendaciones para textura {textura_predominante}:</b>", normal_style))
        for rec in recomendaciones_textura[:4]:
            story.append(Paragraph(f"• {rec}", normal_style))
    elif analisis_tipo == "POTENCIAL_COSECHA":
        potencial_prom = gdf_analisis['potencial_cosecha'].mean()
        if potencial_prom < 15:
            enfoque = "ENFOQUE: MAXIMIZAR COSECHA - Intervención urgente"
        elif potencial_prom < 20:
            enfoque = "ENFOQUE: OPTIMIZAR COSECHA - Mejoras moderadas"
        else:
            enfoque = "ENFOQUE: MANTENER COSECHA - Monitoreo continuo"
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Recomendaciones para Potencial de Cosecha:</b>", normal_style))
        story.append(Paragraph("• Asegurar disponibilidad de agua (riego si precipitación < 150 mm/mes)", normal_style))
        story.append(Paragraph("• Optimizar nutrición (NPK según análisis)", normal_style))
        story.append(Paragraph("• Manejar sombra para evitar estrés por radiación excesiva", normal_style))
        story.append(Paragraph("• Monitorear NDVI continuamente con PlanetScope", normal_style))
    else:
        categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
        if categoria_promedio in ["MUY BAJA", "BAJA"]:
            enfoque = "ENFOQUE: RECUPERACIÓN Y REGENERACIÓN - Intensidad: Alta"
        elif categoria_promedio in ["MEDIA"]:
            enfoque = "ENFOQUE: MANTENIMIENTO Y MEJORA - Intensidad: Media"
        else:
            enfoque = "ENFOQUE: CONSERVACIÓN Y OPTIMIZACIÓN - Intensidad: Baja"
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        recomendaciones = RECOMENDACIONES_AGROECOLOGICAS.get(cultivo, {})
        for categoria_rec, items in recomendaciones.items():
            story.append(Paragraph(f"<b>{categoria_rec.replace('_', ' ').title()}:</b>", normal_style))
            for item in items[:3]:
                story.append(Paragraph(f"• {item}", normal_style))
            story.append(Spacer(1, 5))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>PLAN DE IMPLEMENTACIÓN:</b>", normal_style))
    planes = [
        ("INMEDIATO (0-15 días)", [
            "Preparación del terreno",
            "Siembra de abonos verdes", 
            "Aplicación de biofertilizantes"
        ]),
        ("CORTO PLAZO (1-3 meses)", [
            "Establecimiento coberturas",
            "Monitoreo inicial",
            "Ajustes de manejo"
        ]),
        ("MEDIANO PLAZO (3-12 meses)", [
            "Evaluación de resultados",
            "Diversificación",
            "Optimización del sistema"
        ])
    ]
    for periodo, acciones in planes:
        story.append(Paragraph(f"<b>{periodo}:</b>", normal_style))
        for accion in acciones:
            story.append(Paragraph(f"• {accion}", normal_style))
        story.append(Spacer(1, 5))
    story.append(Spacer(1, 20))
    story.append(Paragraph("INFORMACIÓN ADICIONAL", heading_style))
    story.append(Paragraph("Este informe fue generado automáticamente por el Sistema de Análisis Agrícola GEE.", normal_style))
    story.append(Paragraph("Para consultas técnicas o información detallada, contacte con el departamento técnico.", normal_style))
    doc.build(story)
    buffer.seek(0)
    return buffer

def mostrar_resultados_textura():
    if st.session_state.analisis_textura is None:
        st.warning("No hay datos de análisis de textura disponibles")
        return
    gdf_textura = st.session_state.analisis_textura
    area_total = st.session_state.area_total
    cultivo = st.session_state.cultivo
    mes_analisis = st.session_state.mes_analisis
    st.markdown("## 🏗️ ANÁLISIS DE TEXTURA DEL SUELO")
    if st.button("⬅️ Volver a Configuración", key="volver_textura"):
        st.session_state.analisis_completado = False
        st.rerun()
    st.subheader("📊 Estadísticas del Análisis de Textura")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "NO_DETERMINADA"
        st.metric("🏗️ Textura Predominante", textura_predominante)
    with col2:
        avg_adecuacion = gdf_textura['adecuacion_textura'].mean()
        st.metric("📊 Adecuación Promedio", f"{avg_adecuacion:.1%}")
    with col3:
        avg_arena = gdf_textura['arena'].mean()
        st.metric("🏖️ Arena Promedio", f"{avg_arena:.1f}%")
    with col4:
        avg_arcilla = gdf_textura['arcilla'].mean()
        st.metric("🧱 Arcilla Promedio", f"{avg_arcilla:.1f}%")
    col5, col6, col7 = st.columns(3)
    with col5:
        avg_limo = gdf_textura['limo'].mean()
        st.metric("🌫️ Limo Promedio", f"{avg_limo:.1f}%")
    with col6:
        avg_agua_disp = gdf_textura['agua_disponible'].mean()
        st.metric("💧 Agua Disponible Promedio", f"{avg_agua_disp:.0f} mm/m")
    with col7:
        avg_densidad = gdf_textura['densidad_aparente'].mean()
        st.metric("⚖️ Densidad Aparente", f"{avg_densidad:.2f} g/cm³")
    st.subheader("📋 Distribución de Texturas del Suelo")
    textura_dist = gdf_textura['textura_suelo'].value_counts()
    st.bar_chart(textura_dist)
    st.subheader("🔺 Composición Granulométrica Promedio")
    fig, ax = plt.subplots()
    composicion = [
        gdf_textura['arena'].mean(),
        gdf_textura['limo'].mean(), 
        gdf_textura['arcilla'].mean()
    ]
    labels = ['Arena', 'Limo', 'Arcilla']
    colors = ['#d8b365', '#f6e8c3', '#01665e']
    ax.pie(composicion, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.set_title('Composición Promedio del Suelo')
    st.pyplot(fig)
    st.subheader("🗺️ Mapa de Texturas del Suelo")
    mapa_textura = crear_mapa_interactivo(
        gdf_textura, 
        f"Textura del Suelo - {cultivo.replace('_', ' ').title()}", 
        'textura_suelo', 
        "ANÁLISIS DE TEXTURA"
    )
    st_folium(mapa_textura, width=800, height=500)
    st.subheader("📋 Tabla de Resultados por Zona")
    columnas_textura = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla', 'capacidad_campo', 'agua_disponible']
    df_textura = gdf_textura[columnas_textura].copy()
    df_textura['area_ha'] = df_textura['area_ha'].round(3)
    df_textura['arena'] = df_textura['arena'].round(1)
    df_textura['limo'] = df_textura['limo'].round(1)
    df_textura['arcilla'] = df_textura['arcilla'].round(1)
    df_textura['capacidad_campo'] = df_textura['capacidad_campo'].round(1)
    df_textura['agua_disponible'] = df_textura['agua_disponible'].round(1)
    st.dataframe(df_textura, use_container_width=True)
    textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "Franco"
    adecuacion_promedio = gdf_textura['adecuacion_textura'].mean()
    textura_data = {
        'textura_predominante': textura_predominante,
        'adecuacion_promedio': adecuacion_promedio
    }
    mostrar_recomendaciones_agroecologicas(
        cultivo, "", area_total, "ANÁLISIS DE TEXTURA", None, textura_data
    )
    st.markdown("### 💾 Descargar Resultados")
    col1, col2, col3 = st.columns(3)
    with col1:
        columnas_descarga = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']
        df_descarga = gdf_textura[columnas_descarga].copy()
        df_descarga['area_ha'] = df_descarga['area_ha'].round(3)
        df_descarga['adecuacion_textura'] = df_descarga['adecuacion_textura'].round(3)
        df_descarga['arena'] = df_descarga['arena'].round(1)
        df_descarga['limo'] = df_descarga['limo'].round(1)
        df_descarga['arcilla'] = df_descarga['arcilla'].round(1)
        csv = df_descarga.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Tabla CSV",
            data=csv,
            file_name=f"textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    with col2:
        geojson = gdf_textura.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    with col3:
        if st.button("📄 Generar Informe PDF", type="primary", key="pdf_textura"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_textura, cultivo, "ANÁLISIS DE TEXTURA", "", mes_analisis, area_total, gdf_textura
                )
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

def mostrar_resultados_principales():
    gdf_analisis = st.session_state.gdf_analisis
    area_total = st.session_state.area_total
    cultivo = st.session_state.cultivo
    analisis_tipo = st.session_state.analisis_tipo
    nutriente = st.session_state.nutriente
    mes_analisis = st.session_state.mes_analisis
    st.markdown("## 📈 RESULTADOS DEL ANÁLISIS PRINCIPAL")
    if st.button("⬅️ Volver a Configuración", key="volver_principal"):
        st.session_state.analisis_completado = False
        st.rerun()
    st.subheader("📊 Estadísticas del Análisis")
    if analisis_tipo == "FERTILIDAD ACTUAL":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            avg_fert = gdf_analisis['indice_fertilidad'].mean()
            st.metric("📊 Índice Fertilidad Promedio", f"{avg_fert:.3f}")
        with col2:
            avg_n = gdf_analisis['nitrogeno'].mean()
            st.metric("🌿 Nitrógeno Promedio", f"{avg_n:.1f} kg/ha")
        with col3:
            avg_p = gdf_analisis['fosforo'].mean()
            st.metric("🧪 Fósforo Promedio", f"{avg_p:.1f} kg/ha")
        with col4:
            avg_k = gdf_analisis['potasio'].mean()
            st.metric("⚡ Potasio Promedio", f"{avg_k:.1f} kg/ha")
        col5, col6, col7 = st.columns(3)
        with col5:
            avg_mo = gdf_analisis['materia_organica'].mean()
            st.metric("🌱 Materia Orgánica Promedio", f"{avg_mo:.1f}%")
        with col6:
            avg_ndvi = gdf_analisis['ndvi'].mean()
            st.metric("📡 NDVI Promedio", f"{avg_ndvi:.3f}")
        with col7:
            zona_prioridad = gdf_analisis['prioridad'].value_counts().index[0]
            st.metric("🎯 Prioridad Predominante", zona_prioridad)
        st.subheader("📋 Distribución de Categorías de Fertilidad")
        cat_dist = gdf_analisis['categoria'].value_counts()
        st.bar_chart(cat_dist)
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_rec = gdf_analisis['recomendacion_npk'].mean()
            st.metric(f"💡 Recomendación {nutriente} Promedio", f"{avg_rec:.1f} kg/ha")
        with col2:
            total_rec = (gdf_analisis['recomendacion_npk'] * gdf_analisis['area_ha']).sum()
            st.metric(f"📦 Total {nutriente} Requerido", f"{total_rec:.1f} kg")
        with col3:
            zona_prioridad = gdf_analisis['prioridad'].value_counts().index[0]
            st.metric("🎯 Prioridad Aplicación", zona_prioridad)
        st.subheader("🌿 Estado Actual de Nutrientes")
        col_n, col_p, col_k, col_mo = st.columns(4)
        with col_n:
            avg_n = gdf_analisis['nitrogeno'].mean()
            st.metric("Nitrógeno", f"{avg_n:.1f} kg/ha")
        with col_p:
            avg_p = gdf_analisis['fosforo'].mean()
            st.metric("Fósforo", f"{avg_p:.1f} kg/ha")
        with col_k:
            avg_k = gdf_analisis['potasio'].mean()
            st.metric("Potasio", f"{avg_k:.1f} kg/ha")
        with col_mo:
            avg_mo = gdf_analisis['materia_organica'].mean()
            st.metric("Materia Orgánica", f"{avg_mo:.1f}%")
    st.markdown("### 🗺️ Mapas de Análisis")
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columna_visualizar = 'indice_fertilidad'
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
    else:
        columna_visualizar = 'recomendacion_npk'
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
    mapa_analisis = crear_mapa_interactivo(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    st_folium(mapa_analisis, width=800, height=500)
    st.markdown("### 📄 Mapa para Reporte")
    mapa_estatico = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    if mapa_estatico:
        st.image(mapa_estatico, caption=titulo_mapa, use_column_width=True)
    st.markdown("### 📋 Tabla de Resultados por Zona")
    columnas_tabla = ['id_zona', 'area_ha', 'categoria', 'prioridad']
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'materia_organica', 'ndvi'])
    else:
        columnas_tabla.extend(['recomendacion_npk', 'deficit_npk', 'nitrogeno', 'fosforo', 'potasio'])
    df_tabla = gdf_analisis[columnas_tabla].copy()
    df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
        df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
        df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
        df_tabla['potasio'] = df_tabla['potasio'].round(1)
        df_tabla['materia_organica'] = df_tabla['materia_organica'].round(1)
        df_tabla['ndvi'] = df_tabla['ndvi'].round(3)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
        df_tabla['deficit_npk'] = df_tabla['deficit_npk'].round(1)
    st.dataframe(df_tabla, use_container_width=True)
    categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
    mostrar_recomendaciones_agroecologicas(
        cultivo, categoria_promedio, area_total, analisis_tipo, nutriente
    )
    st.markdown("### 💾 Descargar Resultados")
    col1, col2, col3 = st.columns(3)
    with col1:
        csv = df_tabla.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Tabla CSV",
            data=csv,
            file_name=f"resultados_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    with col2:
        geojson = gdf_analisis.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"zonas_analisis_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    with col3:
        if st.button("📄 Generar Informe PDF", type="primary", key="pdf_principal"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total, st.session_state.analisis_textura
                )
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )

def mostrar_modo_demo():
    st.markdown("### 🚀 Modo Demostración")
    st.info("""
    **Para usar la aplicación:**
    1. Sube un archivo ZIP con el shapefile de tu parcela
    2. Selecciona el cultivo y tipo de análisis
    3. Configura los parámetros en el sidebar
    4. Ejecuta el análisis GEE

    **NUEVO:**
    - 🌍 Datos climáticos de NASA POWER (radiación, lluvia, viento)
    - 🛰️ Datos simulados de PlanetScope (NDVI, EVI, LAI)
    - 🌴 Potencial de cosecha de palma aceitera
    - 📊 Fertilidad, textura y agroecología

    **📁 El shapefile debe incluir:**
    - .shp (geometrías)
    - .shx (índice)
    - .dbf (atributos)
    - .prj (sistema de coordenadas)
    """)
    if st.button("🎯 Cargar Datos de Demostración", type="primary"):
        st.session_state.datos_demo = True
        poligono_ejemplo = Polygon([
            [-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], [-74.1, 4.7], [-74.1, 4.6]
        ])
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo']},
            geometry=[poligono_ejemplo],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo
        st.rerun()

def mostrar_configuracion_parcela():
    gdf_original = st.session_state.gdf_original
    cultivo = st.session_state.cultivo
    n_divisiones = st.session_state.n_divisiones
    area_total = calcular_superficie(gdf_original)
    num_poligonos = len(gdf_original) if gdf_original is not None else 0
    st.success("✅ Parcela cargada correctamente")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
    with col2:
        st.metric("🔢 Número de Polígonos", num_poligonos)
    with col3:
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    st.markdown("### 🗺️ Visualizador de Parcela")
    st.info("🗺️ **Mapa base:** OpenStreetMap. Usa el control de capas para cambiar a ESRI Satélite o otras opciones.")
    mapa_parcela = crear_mapa_visualizador_parcela(gdf_original)
    st_folium(mapa_parcela, width=800, height=500)
    st.markdown("### 📊 División en Zonas de Manejo")
    st.info(f"La parcela se dividirá en **{n_divisiones} zonas** para análisis detallado")
    if st.button("🚀 Ejecutar Análisis GEE Completo", type="primary"):
        with st.spinner("🔄 Dividiendo parcela en zonas..."):
            gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
            st.session_state.gdf_zonas = gdf_zonas
        with st.spinner("🔬 Realizando análisis GEE..."):
            analisis_tipo = st.session_state.analisis_tipo
            nutriente = st.session_state.nutriente
            mes_analisis = st.session_state.mes_analisis
            cultivo = st.session_state.cultivo
            
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                gdf_textura = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                st.session_state.analisis_textura = gdf_textura
                st.session_state.gdf_analisis = gdf_zonas  # Para mantener consistencia
            else:
                gdf_fert = calcular_indices_gee(gdf_zonas, cultivo, mes_analisis, analisis_tipo, nutriiente)
                st.session_state.gdf_analisis = gdf_fert
                
                # Análisis de textura siempre se hace
                gdf_textura = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                st.session_state.analisis_textura = gdf_textura
                
                # Potencial de cosecha (solo para palma)
                if cultivo == "PALMA_ACEITERA" and analisis_tipo in ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"]:
                    centroid = gdf_original.geometry.centroid.iloc[0]
                    datos_clima = obtener_datos_nasa_power(centroid.y, centroid.x, mes_analisis)
                    datos_planetscope = obtener_datos_planetscope(centroid.y, centroid.x)
                    gdf_fert = calcular_potencial_cosecha(gdf_fert, datos_clima, datos_planetscope, cultivo)
                    st.session_state.gdf_analisis = gdf_fert
                    st.session_state.datos_clima = datos_clima
                    st.session_state.datos_planetscope = datos_planetscope
                    
            st.session_state.area_total = area_total
            st.session_state.analisis_completado = True
        st.rerun()

# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    st.session_state.cultivo = st.selectbox("Cultivo:", 
                          ["PALMA_ACEITERA", "CACAO", "BANANO"])
    st.session_state.analisis_tipo = st.selectbox("Tipo de Análisis:", 
                               ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK", "ANÁLISIS DE TEXTURA"])
    st.session_state.nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    st.session_state.mes_analisis = st.selectbox("Mes de Análisis:", 
                               ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                                "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"])
    st.session_state.n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=32, value=24)
    st.subheader("📤 Subir Parcela")
    uploaded_file = st.file_uploader("Subir ZIP con shapefile o archivo KML de tu parcela", type=['zip', 'kml'])
    
    # Opción para API de Planet (opcional)
    st.subheader("🛰️ PlanetScope (opcional)")
    planet_api_key = st.text_input("API Key de Planet (opcional)", type="password")
    st.info("Si no proporcionas una API key, se usarán datos simulados realistas.")
    
    if st.button("🔄 Reiniciar Análisis"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ============================================================================
# MAIN
# ============================================================================
def main():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🌍 NASA POWER + PlanetScope")
    st.sidebar.info("""
    **Datos integrados:**
    - ☀️ Radiación solar (MJ/m²/día)
    - 🌧️ Precipitación (mm/día)
    - 💨 Velocidad del viento (m/s)
    - 🛰️ NDVI, EVI, LAI (PlanetScope)
    
    **Solo para PALMA ACEITERA:**
    - 📈 Potencial de cosecha (ton/ha/año)
    """)
    
    if uploaded_file is not None and not st.session_state.analisis_completado:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
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
        
    if st.session_state.analisis_completado:
        cultivo = st.session_state.cultivo
        if cultivo == "PALMA_ACEITERA" and st.session_state.analisis_tipo in ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"]:
            # Mostrar las tres pestañas
            tab1, tab2, tab3 = st.tabs(["📊 Análisis Principal", "🏗️ Análisis de Textura", "📈 Potencial de Cosecha"])
            with tab1:
                mostrar_resultados_principales()
            with tab2:
                if st.session_state.analisis_textura is not None:
                    mostrar_resultados_textura()
                else:
                    st.info("Ejecuta el análisis principal para obtener datos de textura")
            with tab3:
                mostrar_potencial_cosecha()
        else:
            # Solo dos pestañas
            if st.session_state.analisis_tipo == "ANÁLISIS DE TEXTURA":
                mostrar_resultados_textura()
            else:
                tab1, tab2 = st.tabs(["📊 Análisis Principal", "🏗️ Análisis de Textura"])
                with tab1:
                    mostrar_resultados_principales()
                with tab2:
                    if st.session_state.analisis_textura is not None:
                        mostrar_resultados_textura()
                    else:
                        st.info("Ejecuta el análisis principal para obtener datos de textura")
    elif st.session_state.gdf_original is not None:
        mostrar_configuracion_parcela()
    else:
        mostrar_modo_demo()

if __name__ == "__main__":
    main()
