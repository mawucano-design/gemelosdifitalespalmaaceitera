import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import io
from shapely.geometry import Polygon, Point
import math
import folium
from folium import plugins
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import base64
import fiona
import requests
import warnings
import plotly.express as px
import plotly.graph_objects as go

# Suprimir advertencias molestas
warnings.filterwarnings("ignore", message=".*initial implementation of Parquet.*")

# === PALETA DE COLORES MODERNA ===
COLORS = {
    'primary': '#2E7D32',
    'secondary': '#4CAF50',
    'accent': '#81C784',
    'warning': '#FF9800',
    'danger': '#F44336',
    'info': '#2196F3',
    'card_bg': '#FFFFFF',
    'text': '#2C3E50',
    'border': '#E0E0E0',
    'background_light': '#F9F9F9'
}

# === CSS PERSONALIZADO ===
def inject_custom_css():
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {COLORS['background_light']}; }}
    .metric-card {{
        background: {COLORS['card_bg']};
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        border-left: 4px solid {COLORS['primary']};
        margin: 8px 0;
        transition: transform 0.2s;
    }}
    .metric-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }}
    .metric-title {{ color: {COLORS['text']}; font-size: 14px; font-weight: 500; margin-bottom: 8px; }}
    .metric-value {{ color: {COLORS['primary']}; font-size: 28px; font-weight: 700; margin: 0; }}
    .metric-delta {{ color: {COLORS['secondary']}; font-size: 14px; margin-top: 4px; }}
    h1, h2, h3, h4 {{ color: {COLORS['text']}; font-weight: 600; }}
    .stButton>button {{
        background-color: {COLORS['primary']};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 20px;
    }}
    .stButton>button:hover {{ background-color: #1B5E20; color: white; }}
    </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="🌴 Analizador Cultivos", layout="wide")
inject_custom_css()
st.title("🌱 ANALIZADOR CULTIVOS - DIGITAL TWIN CON NASA POWER + PLANETSCOPE")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# PARÁMETROS MEJORADOS Y MÁS REALISTAS PARA DIFERENTES CULTIVOS
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

FACTORES_N_MES = FACTORES_MES.copy()
FACTORES_P_MES = FACTORES_MES.copy()
FACTORES_K_MES = FACTORES_MES.copy()

# PALETAS
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
    'FOSFORO': ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
    'POTASIO': ['#4d004b', '#810f7c', '#8c6bb1', '#8c96c6', '#9ebcda', '#bfd3e6', '#e0ecf4', '#edf8fb'],
    'TEXTURA': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'],
    'POTENCIAL': ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b']
}

# RECOMENDACIONES
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

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================
def calcular_superficie(gdf):
    try:
        if gdf is None or gdf.empty or gdf.geometry.isnull().all():
            return 0.0
        if gdf.crs and gdf.crs.is_geographic:
            crs_options = ['EPSG:3116', 'EPSG:3857', 'EPSG:32719', 'EPSG:32718', 'EPSG:5367']
            for crs_code in crs_options:
                try:
                    gdf_proj = gdf.to_crs(crs_code)
                    area_m2 = gdf_proj.geometry.area.sum()
                    break
                except:
                    continue
            else:
                centro = gdf.geometry.centroid.iloc[0]
                lat_rad = math.radians(centro.y)
                m_per_degree_lat = 111319.9
                m_per_degree_lon = 111319.9 * math.cos(lat_rad)
                bounds = gdf.total_bounds
                width_deg = bounds[2] - bounds[0]
                height_deg = bounds[3] - bounds[1]
                area_m2 = abs(width_deg * m_per_degree_lon * height_deg * m_per_degree_lat)
        else:
            area_m2 = gdf.geometry.area.sum()
        area_ha = area_m2 / 10000
        return float(area_ha) if not np.isnan(area_ha) else 0.0
    except Exception as e:
        st.warning(f"Advertencia en cálculo de área: {str(e)}")
        return 0.0

def procesar_archivo(uploaded_file):
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
                    gdf = gpd.read_file(os.path.join(tmp_dir, shp_files[0]))
                elif kml_files:
                    gdf = gpd.read_file(os.path.join(tmp_dir, kml_files[0]), driver='KML')
                else:
                    return None
            if not gdf.is_valid.all():
                gdf = gdf.make_valid()
            return gdf
    except Exception as e:
        st.error(f"Error procesando archivo: {str(e)}")
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

# ============================================================================
# FUNCIONES DE DATOS SATELITALES Y CLIMÁTICOS
# ============================================================================
def obtener_datos_satelitales(lat, lon, fecha_analisis, cultivo):
    seed = abs(hash(f"{lat:.4f}_{lon:.4f}_{fecha_analisis}_{cultivo}")) % (2**32)
    rng = np.random.RandomState(seed)
    base_ndvi = {'PALMA_ACEITERA': 0.65, 'CACAO': 0.55, 'BANANO': 0.70}.get(cultivo, 0.6)
    base_evi = base_ndvi * 0.8
    base_lai = {'PALMA_ACEITERA': 4.0, 'CACAO': 3.0, 'BANANO': 5.0}.get(cultivo, 4.0)
    mes = fecha_analisis.month
    estacional = 1.0 + 0.3 * np.sin(2 * np.pi * (mes - 1) / 12)
    ndvi = np.clip(rng.normal(base_ndvi * estacional, 0.08), 0.2, 0.9)
    evi = np.clip(rng.normal(base_evi * estacional, 0.07), 0.15, 0.8)
    lai = np.clip(rng.normal(base_lai * estacional, 0.6), 1.0, 8.0)
    savi = np.clip(ndvi * (1 + 0.5) / (1 + ndvi + 0.5), 0.1, 0.85)
    return {
        'ndvi': ndvi,
        'evi': evi,
        'lai': lai,
        'savi': savi,
        'fuente': 'Sentinel-2 + PlanetScope (simulado realista)'
    }

def obtener_datos_nasa_power(lat, lon, mes_analisis):
    """Obtiene datos climáticos de NASA POWER con protección contra valores negativos."""
    try:
        mes_num = {
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
            "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
        }[mes_analisis]
        año = datetime.now().year
        start = f"{año}{mes_num:02d}01"
        end = f"{año}{mes_num+1:02d}01" if mes_num < 12 else f"{año+1}0101"
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            "parameters": "ALLSKY_SFC_SW_DWN,PRECTOTCORR,WS10M,RH2M",
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
            rad_solar = float(np.nanmean(list(dias['ALLSKY_SFC_SW_DWN'].values())))
            precip = float(np.nanmean(list(dias['PRECTOTCORR'].values())))
            viento = float(np.nanmean(list(dias['WS10M'].values())))
            humedad = float(np.nanmean(list(dias['RH2M'].values())))
            return {
                'radiacion_solar': max(0.0, rad_solar),
                'precipitacion': max(0.0, precip),
                'velocidad_viento': max(0.0, viento),
                'humedad_relativa': np.clip(humedad, 0, 100)
            }
    except:
        pass
    return {
        'radiacion_solar': 16.0,
        'precipitacion': 6.0,
        'velocidad_viento': 2.5,
        'humedad_relativa': 70.0
    }

def obtener_datos_nasa_power_historicos(lat, lon, years=10):
    """Obtiene datos climáticos mensuales promedio de los últimos N años."""
    try:
        current_year = datetime.now().year
        years_range = range(current_year - years, current_year + 1)
        all_data = {
            'precipitacion': [],
            'radiacion_solar': [],
            'velocidad_viento': [],
            'humedad_relativa': []
        }
        for year in years_range:
            for mes_num in range(1, 13):
                start = f"{year}{mes_num:02d}01"
                end = f"{year}{mes_num+1:02d}01" if mes_num < 12 else f"{year+1}0101"
                url = "https://power.larc.nasa.gov/api/temporal/daily/point"
                params = {
                    "parameters": "ALLSKY_SFC_SW_DWN,PRECTOTCORR,WS10M,RH2M",
                    "community": "ag",
                    "longitude": lon,
                    "latitude": lat,
                    "start": start,
                    "end": end,
                    "format": "json"
                }
                try:
                    response = requests.get(url, params=params, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        dias = data['properties']['parameter']
                        rad = np.nanmean(list(dias['ALLSKY_SFC_SW_DWN'].values()))
                        precip = np.nanmean(list(dias['PRECTOTCORR'].values()))
                        viento = np.nanmean(list(dias['WS10M'].values()))
                        humedad = np.nanmean(list(dias['RH2M'].values()))
                        if not np.isnan(rad): all_data['radiacion_solar'].append(float(rad))
                        if not np.isnan(precip): all_data['precipitacion'].append(float(precip))
                        if not np.isnan(viento): all_data['velocidad_viento'].append(float(viento))
                        if not np.isnan(humedad): all_data['humedad_relativa'].append(float(humedad))
                except:
                    continue
        
        # Promediar por mes
        for key in all_data:
            if len(all_data[key]) >= 12:
                arr = np.array(all_data[key])
                monthly_avg = []
                for mes in range(12):
                    monthly_vals = arr[mes::12]
                    avg_val = np.nanmean(monthly_vals) if len(monthly_vals) > 0 and not np.isnan(np.nanmean(monthly_vals)) else 0
                    if key == 'humedad_relativa':
                        monthly_avg.append(np.clip(avg_val, 0, 100))
                    else:
                        monthly_avg.append(max(0, avg_val))
                all_data[key] = monthly_avg
            else:
                # Valores por defecto
                if key == 'precipitacion': all_data[key] = [6.0] * 12
                elif key == 'radiacion_solar': all_data[key] = [16.0] * 12
                elif key == 'velocidad_viento': all_data[key] = [2.5] * 12
                else: all_data[key] = [70.0] * 12
        return all_data
    except Exception as e:
        st.warning(f"⚠️ Error en datos históricos: usando valores por defecto.")
        return {
            'precipitacion': [6.0] * 12,
            'radiacion_solar': [16.0] * 12,
            'velocidad_viento': [2.5] * 12,
            'humedad_relativa': [70.0] * 12
        }

def calcular_potencial_cosecha(gdf_analisis, datos_clima, datos_satelitales, cultivo):
    if cultivo != "PALMA_ACEITERA":
        gdf_analisis['potencial_cosecha'] = 0.0
        return gdf_analisis
    
    # Valores saneados
    rad_solar = max(0.0, datos_clima.get('radiacion_solar', 16.0))
    precip_diaria = max(0.0, datos_clima.get('precipitacion', 6.0))
    viento = max(0.0, datos_clima.get('velocidad_viento', 2.5))
    ndvi = np.clip(datos_satelitales.get('ndvi', 0.6), 0.1, 0.9)
    
    factor_rad = min(1.0, rad_solar / 20.0) if rad_solar > 0 else 0.0
    precip_mensual = precip_diaria * 30
    factor_agua = min(1.0, precip_mensual / 200.0) if precip_mensual > 0 else 0.0
    factor_viento = max(0.7, 1.0 - (viento - 2.0) / 10.0) if viento >= 0 else 1.0
    factor_ndvi = min(1.0, ndvi / 0.8) if ndvi > 0 else 0.0
    
    if 'indice_fertilidad' not in gdf_analisis.columns:
        gdf_analisis['indice_fertilidad'] = 0.6
    factor_suelo = gdf_analisis['indice_fertilidad'].clip(0, 1)
    
    potencial_base = 25.0
    gdf_analisis['potencial_cosecha'] = (
        potencial_base * 
        factor_suelo * 
        factor_rad * 
        factor_agua * 
        factor_viento * 
        factor_ndvi
    ).clip(0, 50)
    
    # Guardar datos saneados
    for key, value in datos_clima.items():
        gdf_analisis[key] = max(0, value) if key != 'humedad_relativa' else np.clip(value, 0, 100)
    for key, value in datos_satelitales.items():
        gdf_analisis[key] = value
    
    if 'id_zona' not in gdf_analisis.columns:
        gdf_analisis['id_zona'] = gdf_analisis.index + 1
    
    return gdf_analisis

# ============================================================================
# FUNCIONES DE ANÁLISIS
# ============================================================================
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
            centroid = row.geometry.centroid if hasattr(row.geometry, 'centroid') else row.geometry.representative_point()
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_textura")) % (2**32)
            rng = np.random.RandomState(seed_value)
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            variabilidad_local = 0.15 + 0.7 * (lat_norm * lon_norm)
            
            arena_optima = params_textura['arena_optima']
            limo_optima = params_textura['limo_optima']
            arcilla_optima = params_textura['arcilla_optima']
            
            arena = max(5, min(95, rng.normal(arena_optima * (0.8 + 0.4 * variabilidad_local), arena_optima * 0.2)))
            limo = max(5, min(95, rng.normal(limo_optima * (0.7 + 0.6 * variabilidad_local), limo_optima * 0.25)))
            arcilla = max(5, min(95, rng.normal(arcilla_optima * (0.75 + 0.5 * variabilidad_local), arcilla_optima * 0.3)))
            
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
            
            for k, v in propiedades_fisicas.items():
                zonas_gdf.loc[idx, k] = v
                
        except Exception as e:
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]])
            zonas_gdf.loc[idx, 'area_ha'] = area_ha
            zonas_gdf.loc[idx, 'arena'] = params_textura['arena_optima']
            zonas_gdf.loc[idx, 'limo'] = params_textura['limo_optima']
            zonas_gdf.loc[idx, 'arcilla'] = params_textura['arcilla_optima']
            zonas_gdf.loc[idx, 'textura_suelo'] = params_textura['textura_optima']
            zonas_gdf.loc[idx, 'adecuacion_textura'] = 1.0
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = "ÓPTIMA"
            propiedades_default = calcular_propiedades_fisicas_suelo(params_textura['textura_optima'], 3.0)
            for k, v in propiedades_default.items():
                zonas_gdf.loc[idx, k] = v
    
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
        
        sub_poligonos = []
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

def calcular_indices_gee(gdf, cultivo, mes_analisis, analisis_tipo, nutriente, ndvi_base=None, evi_base=None):
    params = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    
    # Usar los nombres correctos
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
            centroid = row.geometry.centroid if hasattr(row.geometry, 'centroid') else row.geometry.representative_point()
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}")) % (2**32)
            rng = np.random.RandomState(seed_value)
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            variabilidad_local = 0.2 + 0.6 * (lat_norm * lon_norm)
            
            n_optimo = params['NITROGENO']['optimo']
            p_optimo = params['FOSFORO']['optimo']
            k_optimo = params['POTASIO']['optimo']
            
            nitrogeno = max(0, rng.normal(n_optimo * (0.8 + 0.4 * variabilidad_local), n_optimo * 0.15))
            fosforo = max(0, rng.normal(p_optimo * (0.7 + 0.6 * variabilidad_local), p_optimo * 0.2))
            potasio = max(0, rng.normal(k_optimo * (0.75 + 0.5 * variabilidad_local), k_optimo * 0.18))
            
            nitrogeno *= factor_n_mes * (0.9 + 0.2 * rng.random())
            fosforo *= factor_p_mes * (0.9 + 0.2 * rng.random())
            potasio *= factor_k_mes * (0.9 + 0.2 * rng.random())
            
            materia_organica = max(1.0, min(8.0, rng.normal(params['MATERIA_ORGANICA_OPTIMA'], 1.0)))
            humedad = max(0.1, min(0.8, rng.normal(params['HUMEDAD_OPTIMA'], 0.1)))
            ph = max(4.0, min(8.0, rng.normal(params['pH_OPTIMO'], 0.5)))
            conductividad = max(0.1, min(3.0, rng.normal(params['CONDUCTIVIDAD_OPTIMA'], 0.3)))
            
            if ndvi_base is not None:
                ndvi = np.clip(rng.normal(ndvi_base, 0.05), 0.1, 0.95)
            elif evi_base is not None:
                base_ndvi = evi_base / 0.8
                ndvi = np.clip(rng.normal(base_ndvi, 0.05), 0.1, 0.95)
            else:
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
            
        except Exception as e:
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

# ============================================================================
# FUNCIONES DE VISUALIZACIÓN
# ============================================================================
def crear_mapa_interactivo_esri(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    if len(gdf) == 0:
        return None
    
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=15,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite'
    )
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Calles',
        overlay=False
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
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
        elif analisis_tipo == "CLIMÁTICO":
            if nutriente == "RAD":
                vmin, vmax = 10, 25
                unidad = "MJ/m²/día"
            elif nutriente == "PRECIP":
                vmin, vmax = 0, 15
                unidad = "mm/día"
            elif nutriente == "VIENTO":
                vmin, vmax = 0, 5
                unidad = "m/s"
            else:  # HUMEDAD
                vmin, vmax = 40, 100
                unidad = "%"
            colores = ['#253494', '#2c7fb8', '#41b6c4', '#a1dab4', '#ffffcc']
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
                textura = row.get(columna_valor, "NO_DETERMINADA")
                color = colores_textura.get(textura, '#999999')
                valor_display = textura
            else:
                valor = row.get(columna_valor, 0)
                color = obtener_color(valor, vmin, vmax, colores)
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    valor_display = f"{valor:.3f}"
                elif analisis_tipo == "CLIMÁTICO":
                    valor_display = f"{valor:.1f}"
                else:
                    valor_display = f"{valor:.1f}"
            
            # Popup mejorado
            popup_html = f"""
            <div style='font-family: Arial; font-size: 12px; max-width: 300px;'>
                <b>Zona {row.get('id_zona', idx+1)}</b><br>
                <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                <b>Valor:</b> {valor_display} {unidad}
            """
            if analisis_tipo == "FERTILIDAD ACTUAL":
                popup_html += f"<br><b>Categoría:</b> {row.get('categoria', 'N/A')}"
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                popup_html += f"<br><b>Adecuación:</b> {row.get('categoria_adecuacion', 'N/A')}"
            popup_html += "</div>"
            
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.7,
                    'opacity': 0.9
                },
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"Zona {row.get('id_zona', idx+1)}: {valor_display} {unidad}"
            ).add_to(m)
            
            # Marcador con número de zona
            try:
                centroid = row.geometry.centroid
                folium.Marker(
                    [centroid.y, centroid.x],
                    popup=f"Zona {row.get('id_zona', idx+1)}",
                    icon=folium.DivIcon(
                        html=f'<div style="font-size: 10pt; font-weight: bold; color: black; background: white; border-radius: 50%; padding: 2px;">{row.get("id_zona", idx+1)}</div>'
                    )
                ).add_to(m)
            except:
                pass
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
    
    # Leyenda
    if analisis_tipo and columna_valor:
        legend_html = f'''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 150px; height: auto;
                    border:2px solid grey; z-index:9999; font-size:14px;
                    background-color: white; padding: 10px;
                    border-radius: 5px;">
            <b>{titulo}</b><br>
            <b>Unidad:</b> {unidad}<br>
        '''
        
        if analisis_tipo == "ANÁLISIS DE TEXTURA":
            for textura, color in colores_textura.items():
                legend_html += f'<div><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px;"></span> {textura}</div>'
        else:
            for i in range(len(colores)):
                valor = vmin + (i / (len(colores)-1)) * (vmax - vmin)
                legend_html += f'<div><span style="background:{colores[i]}; width:20px; height:15px; display:inline-block; margin-right:5px;"></span> {valor:.1f}</div>'
        
        legend_html += '</div>'
        m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def crear_mapa_visualizador_parcela(gdf):
    if len(gdf) == 0:
        return None
    
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=14,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite'
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
                    textura = row.get(columna_valor, "NO_DETERMINADA")
                    color = colores_textura.get(textura, '#999999')
                    # Para textura, el valor a mostrar es la textura misma
                    texto_valor = textura[:10]  # Mostrar solo primeros 10 caracteres
                else:
                    valor = row.get(columna_valor, 0)
                    valor_norm = (valor - vmin) / (vmax - vmin)
                    valor_norm = max(0, min(1, valor_norm))
                    color = cmap(valor_norm)
                    
                    # Formatear según el tipo de análisis
                    if analisis_tipo == "FERTILIDAD ACTUAL":
                        texto_valor = f"{valor:.3f}"
                    elif analisis_tipo == "POTENCIAL_COSECHA":
                        texto_valor = f"{valor:.1f}"
                    elif analisis_tipo in ["RECOMENDACIONES NPK", "CLIMÁTICO"]:
                        texto_valor = f"{valor:.1f}"
                    else:
                        texto_valor = f"{valor:.0f}"
                
                gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1)
                try:
                    centroid = row.geometry.centroid
                    
                    # Anotación corregida
                    id_zona = row.get('id_zona', idx+1)
                    ax.annotate(f"Z{id_zona}\n{texto_valor}", 
                               (centroid.x, centroid.y), 
                               xytext=(3, 3), textcoords="offset points", 
                               fontsize=6, color='black', weight='bold',
                               bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8),
                               ha='center', va='center')
                except:
                    pass
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
# FUNCIONES DE INTERFAZ Y MAPAS CLIMÁTICOS HISTÓRICOS
# ============================================================================
def crear_mapa_heatmap_climatico(gdf_centroid, datos_historicos, variable, titulo):
    try:
        lat0, lon0 = gdf_centroid.y, gdf_centroid.x
        np.random.seed(42)
        lats = lat0 + np.random.normal(0, 0.01, 50)
        lons = lon0 + np.random.normal(0, 0.01, 50)
        valor_promedio = np.mean(datos_historicos[variable])
        heat_data = []
        
        for lat, lon in zip(lats, lons):
            valor = valor_promedio * np.random.uniform(0.8, 1.2)
            if variable == 'precipitacion':
                peso = np.clip(valor / 20.0, 0.1, 1.0)
            elif variable == 'radiacion_solar':
                peso = np.clip(valor / 25.0, 0.1, 1.0)
            else:
                peso = np.clip(valor / 5.0, 0.1, 1.0)
            heat_data.append([lat, lon, peso])
        
        m = folium.Map(location=[lat0, lon0], zoom_start=12, tiles='OpenStreetMap')
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Esri Satélite'
        ).add_to(m)
        
        if variable == 'precipitacion':
            gradient = {0.2: 'yellow', 0.4: 'lime', 0.6: 'cyan', 0.8: 'blue', 1.0: 'darkblue'}
        elif variable == 'radiacion_solar':
            gradient = {0.2: 'yellow', 0.4: 'orange', 0.6: 'red', 0.8: 'darkred', 1.0: 'black'}
        else:
            gradient = {0.2: 'lightblue', 0.4: 'blue', 0.6: 'darkblue', 0.8: 'purple', 1.0: 'black'}
        
        plugins.HeatMap(
            heat_data,
            name=titulo,
            min_opacity=0.4,
            max_zoom=18,
            radius=30,
            blur=15,
            gradient=gradient
        ).add_to(m)
        
        folium.LayerControl().add_to(m)
        m.fit_bounds([[lat0-0.02, lon0-0.02], [lat0+0.02, lon0+0.02]])
        return m
    except Exception as e:
        st.error(f"❌ Error creando mapa de calor: {str(e)}")
        return None

def mostrar_mapas_climaticos_historicos():
    if not st.session_state.get('datos_clima_historicos'):
        st.warning("⚠️ No hay datos climáticos históricos disponibles.")
        return
    
    datos = st.session_state.datos_clima_historicos
    centroid = st.session_state.gdf_original.geometry.centroid.iloc[0]
    
    st.markdown("## 🌍 Mapas Climáticos Históricos (Últimos 10 Años - NASA POWER)")
    
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    # Precipitación
    st.subheader("🌧️ Mapa de Calor: Precipitación Promedio (mm/día)")
    col1, col2 = st.columns([3, 1])
    with col1:
        mapa_precip = crear_mapa_heatmap_climatico(centroid, datos, 'precipitacion', "Precipitación")
        if mapa_precip:
            st_folium(mapa_precip, width=600, height=400)
    with col2:
        prom_precip = np.mean(datos['precipitacion'])
        st.metric("📊 Promedio Anual", f"{prom_precip*30:.0f} mm/mes")
        if prom_precip*30 < 100:
            st.error("🚨 Bajo")
        elif prom_precip*30 > 300:
            st.warning("⚠️ Alto")
        else:
            st.success("✅ Óptimo")
    
    df_precip = pd.DataFrame({'Mes': meses, 'Precipitación (mm/día)': datos['precipitacion']})
    fig_precip = px.line(df_precip, x='Mes', y='Precipitación (mm/día)', 
                        title="Precipitación Promedio por Mes (Últimos 10 años)")
    st.plotly_chart(fig_precip, use_container_width=True)
    st.markdown("---")
    
    # Radiación Solar
    st.subheader("☀️ Mapa de Calor: Radiación Solar Promedio (MJ/m²/día)")
    col1, col2 = st.columns([3, 1])
    with col1:
        mapa_rad = crear_mapa_heatmap_climatico(centroid, datos, 'radiacion_solar', "Radiación Solar")
        if mapa_rad:
            st_folium(mapa_rad, width=600, height=400)
    with col2:
        prom_rad = np.mean(datos['radiacion_solar'])
        st.metric("📊 Promedio Anual", f"{prom_rad:.1f} MJ/m²/día")
        if prom_rad < 12:
            st.warning("⚠️ Baja")
        elif prom_rad > 22:
            st.warning("⚠️ Alta")
        else:
            st.success("✅ Óptima")
    
    df_rad = pd.DataFrame({'Mes': meses, 'Radiación (MJ/m²/día)': datos['radiacion_solar']})
    fig_rad = px.line(df_rad, x='Mes', y='Radiación (MJ/m²/día)', 
                     title="Radiación Solar Promedio por Mes (Últimos 10 años)")
    st.plotly_chart(fig_rad, use_container_width=True)
    st.markdown("---")
    
    # Viento
    st.subheader("💨 Mapa de Calor: Velocidad del Viento Promedio (m/s)")
    col1, col2 = st.columns([3, 1])
    with col1:
        mapa_viento = crear_mapa_heatmap_climatico(centroid, datos, 'velocidad_viento', "Velocidad del Viento")
        if mapa_viento:
            st_folium(mapa_viento, width=600, height=400)
    with col2:
        prom_viento = np.mean(datos['velocidad_viento'])
        st.metric("📊 Promedio Anual", f"{prom_viento:.1f} m/s")
        if prom_viento > 3.0:
            st.warning("⚠️ Alto")
        else:
            st.success("✅ Aceptable")
    
    df_viento = pd.DataFrame({'Mes': meses, 'Viento (m/s)': datos['velocidad_viento']})
    fig_viento = px.line(df_viento, x='Mes', y='Viento (m/s)', 
                        title="Velocidad del Viento Promedio por Mes (Últimos 10 años)")
    st.plotly_chart(fig_viento, use_container_width=True)

# ============================================================================
# FUNCIONES DE RESULTADOS - CORREGIDAS
# ============================================================================
def mostrar_resultados_principales():
    if st.session_state.gdf_analisis is not None:
        # Métricas resumen
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🌱 Cultivo", st.session_state.cultivo)
        with col2:
            st.metric("📅 Mes", st.session_state.mes_analisis)
        with col3:
            area_total = st.session_state.area_total
            st.metric("📐 Área Total", f"{area_total:.2f} ha")
        with col4:
            n_zonas = len(st.session_state.gdf_analisis)
            st.metric("🔢 Número de Zonas", n_zonas)
        
        # Mapa interactivo
        st.subheader("🗺️ Mapa de Fertilidad Actual")
        mapa_interactivo = crear_mapa_interactivo_esri(
            st.session_state.gdf_analisis,
            "FERTILIDAD ACTUAL",
            columna_valor='indice_fertilidad',
            analisis_tipo="FERTILIDAD ACTUAL",
            nutriente=None
        )
        if mapa_interactivo:
            st_folium(mapa_interactivo, width=800, height=500)
        
        # Mapa estático
        st.subheader("📊 Mapa Estático de Fertilidad")
        mapa_estatico = crear_mapa_estatico(
            st.session_state.gdf_analisis,
            "FERTILIDAD ACTUAL",
            columna_valor='indice_fertilidad',
            analisis_tipo="FERTILIDAD ACTUAL",
            nutriente=None
        )
        if mapa_estatico:
            st.image(mapa_estatico, use_column_width=True)
        
        # Tabla de resultados
        st.subheader("📋 Tabla de Resultados por Zona")
        columnas_mostrar = ['id_zona', 'area_ha', 'nitrogeno', 'fosforo', 'potasio', 
                           'indice_fertilidad', 'categoria', 'prioridad']
        df_display = st.session_state.gdf_analisis[columnas_mostrar].copy()
        df_display['area_ha'] = df_display['area_ha'].round(2)
        df_display['indice_fertilidad'] = df_display['indice_fertilidad'].round(3)
        for col in ['nitrogeno', 'fosforo', 'potasio']:
            df_display[col] = df_display[col].round(1)
        st.dataframe(df_display, use_container_width=True)
        
        # Recomendaciones generales
        st.subheader("💡 Recomendaciones Generales")
        
        # Calcular estadísticas
        avg_fertilidad = st.session_state.gdf_analisis['indice_fertilidad'].mean()
        zonas_bajas = len(st.session_state.gdf_analisis[st.session_state.gdf_analisis['categoria'].isin(['BAJA', 'MUY BAJA'])])
        
        if avg_fertilidad < 0.4:
            st.error("🚨 **ALERTA**: La fertilidad general del suelo es BAJA. Se recomienda:")
            st.markdown("""
            - Aplicar materia orgánica (compost, estiércol)
            - Realizar análisis de suelo más detallado
            - Considerar rotación de cultivos
            - Aplicar fertilización balanceada
            """)
        elif avg_fertilidad < 0.6:
            st.warning("⚠️ **ATENCIÓN**: La fertilidad general del suelo es MEDIA. Se recomienda:")
            st.markdown("""
            - Mantener niveles de materia orgánica
            - Monitoreo periódico de nutrientes
            - Fertilización de mantenimiento
            - Prácticas de conservación de suelo
            """)
        else:
            st.success("✅ **ÓPTIMO**: La fertilidad general del suelo es ALTA. Se recomienda:")
            st.markdown("""
            - Mantener prácticas actuales
            - Monitoreo preventivo
            - Fertilización de mantenimiento
            - Continuar con rotación de cultivos
            """)
        
        if zonas_bajas > 0:
            st.info(f"🔍 **Zonas críticas**: {zonas_bajas} zona(s) requieren atención prioritaria")

def mostrar_resultados_textura():
    if st.session_state.analisis_textura is not None:
        st.subheader("🗺️ Mapa de Textura del Suelo")
        mapa_interactivo = crear_mapa_interactivo_esri(
            st.session_state.analisis_textura,
            "ANÁLISIS DE TEXTURA",
            columna_valor='textura_suelo',
            analisis_tipo="ANÁLISIS DE TEXTURA",
            nutriente=None
        )
        if mapa_interactivo:
            st_folium(mapa_interactivo, width=800, height=500)
        
        # Mapa estático
        mapa_estatico = crear_mapa_estatico(
            st.session_state.analisis_textura,
            "ANÁLISIS DE TEXTURA",
            columna_valor='textura_suelo',
            analisis_tipo="ANÁLISIS DE TEXTURA",
            nutriente=None
        )
        if mapa_estatico:
            st.image(mapa_estatico, use_column_width=True)
        
        # Tabla de resultados
        st.subheader("📋 Tabla de Textura por Zona")
        columnas_mostrar = ['id_zona', 'area_ha', 'arena', 'limo', 'arcilla', 
                           'textura_suelo', 'categoria_adecuacion', 'adecuacion_textura']
        df_display = st.session_state.analisis_textura[columnas_mostrar].copy()
        df_display['area_ha'] = df_display['area_ha'].round(2)
        df_display['adecuacion_textura'] = df_display['adecuacion_textura'].round(2)
        for col in ['arena', 'limo', 'arcilla']:
            df_display[col] = df_display[col].round(1)
        st.dataframe(df_display, use_container_width=True)
        
        # Recomendaciones por textura
        st.subheader("💡 Recomendaciones por Tipo de Textura")
        texturas_unicas = st.session_state.analisis_textura['textura_suelo'].unique()
        for textura in texturas_unicas:
            if textura in RECOMENDACIONES_TEXTURA:
                with st.expander(f"Recomendaciones para suelo {textura}"):
                    for rec in RECOMENDACIONES_TEXTURA[textura]:
                        st.markdown(f"- {rec}")
    else:
        st.warning("No hay datos de textura disponibles.")

def mostrar_potencial_cosecha():
    if st.session_state.gdf_analisis is not None and 'potencial_cosecha' in st.session_state.gdf_analisis.columns:
        st.subheader("🗺️ Mapa de Potencial de Cosecha")
        mapa_interactivo = crear_mapa_interactivo_esri(
            st.session_state.gdf_analisis,
            "POTENCIAL_COSECHA",
            columna_valor='potencial_cosecha',
            analisis_tipo="POTENCIAL_COSECHA",
            nutriente=None
        )
        if mapa_interactivo:
            st_folium(mapa_interactivo, width=800, height=500)
        
        # Mapa estático
        mapa_estatico = crear_mapa_estatico(
            st.session_state.gdf_analisis,
            "POTENCIAL_COSECHA",
            columna_valor='potencial_cosecha',
            analisis_tipo="POTENCIAL_COSECHA",
            nutriente=None
        )
        if mapa_estatico:
            st.image(mapa_estatico, use_column_width=True)
        
        # Tabla de potencial de cosecha
        st.subheader("📋 Potencial de Cosecha por Zona")
        columnas_mostrar = ['id_zona', 'area_ha', 'potencial_cosecha', 'ndvi', 'radiacion_solar', 'precipitacion']
        df_display = st.session_state.gdf_analisis[columnas_mostrar].copy()
        df_display['area_ha'] = df_display['area_ha'].round(2)
        df_display['potencial_cosecha'] = df_display['potencial_cosecha'].round(1)
        df_display['ndvi'] = df_display['ndvi'].round(3)
        df_display['radiacion_solar'] = df_display['radiacion_solar'].round(1)
        df_display['precipitacion'] = df_display['precipitacion'].round(1)
        st.dataframe(df_display, use_container_width=True)
        
        # Recomendaciones para mejorar el potencial
        st.subheader("💡 Recomendaciones para Mejorar el Potencial")
        avg_potencial = st.session_state.gdf_analisis['potencial_cosecha'].mean()
        
        if avg_potencial < 15:
            st.error("🚨 **POTENCIAL BAJO**: Se requiere intervención inmediata")
            st.markdown("""
            - Mejorar fertilidad del suelo
            - Optimizar riego
            - Control de plagas y enfermedades
            - Implementar prácticas de conservación
            """)
        elif avg_potencial < 25:
            st.warning("⚠️ **POTENCIAL MEDIO**: Oportunidad de mejora")
            st.markdown("""
            - Fertilización balanceada
            - Manejo integrado de cultivos
            - Mejorar prácticas agrícolas
            - Monitoreo constante
            """)
        else:
            st.success("✅ **POTENCIAL ALTO**: Excelentes condiciones")
            st.markdown("""
            - Mantener prácticas actuales
            - Monitoreo preventivo
            - Mejoras incrementales
            - Planificación de cosecha
            """)
    else:
        st.warning("No hay datos de potencial de cosecha disponibles. Solo disponible para palma aceitera.")

def mostrar_clima_detalles():
    if st.session_state.datos_clima:
        datos = st.session_state.datos_clima
        st.subheader("🌤️ Datos Climáticos Actuales (NASA POWER)")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("☀️ Radiación Solar", f"{datos['radiacion_solar']:.1f} MJ/m²/día")
        with col2:
            st.metric("🌧️ Precipitación", f"{datos['precipitacion']:.1f} mm/día")
        with col3:
            st.metric("💨 Velocidad Viento", f"{datos['velocidad_viento']:.1f} m/s")
        with col4:
            st.metric("💧 Humedad Relativa", f"{datos['humedad_relativa']:.1f} %")
        
        # Mapa climático interactivo - CORREGIDO
        st.subheader("🗺️ Mapa Climático Interactivo")
        
        # Crear un GeoDataFrame con el centroide y los datos climáticos
        centroid = st.session_state.gdf_original.geometry.centroid.iloc[0]
        
        # Crear un GeoDataFrame con múltiples puntos para visualizar
        # Simulamos variabilidad espacial
        import random
        
        # Crear varios puntos alrededor del centroide
        points = []
        precip_values = []
        
        for i in range(5):
            # Pequeña variación en las coordenadas
            lat_variation = centroid.y + random.uniform(-0.01, 0.01)
            lon_variation = centroid.x + random.uniform(-0.01, 0.01)
            
            # Valor de precipitación con variación
            precip_variation = datos['precipitacion'] * random.uniform(0.8, 1.2)
            
            points.append(Point(lon_variation, lat_variation))
            precip_values.append(precip_variation)
        
        # Crear GeoDataFrame
        gdf_clima = gpd.GeoDataFrame(
            {
                'precipitacion': precip_values,
                'radiacion_solar': [datos['radiacion_solar']] * 5,
                'velocidad_viento': [datos['velocidad_viento']] * 5,
                'humedad_relativa': [datos['humedad_relativa']] * 5
            },
            geometry=points,
            crs=st.session_state.gdf_original.crs
        )
        
        # Añadir id_zona
        gdf_clima['id_zona'] = range(1, len(gdf_clima) + 1)
        
        mapa_clima = crear_mapa_interactivo_esri(
            gdf_clima,
            "CLIMÁTICO",
            columna_valor='precipitacion',
            analisis_tipo="CLIMÁTICO",
            nutriente="PRECIP"
        )
        if mapa_clima:
            st_folium(mapa_clima, width=800, height=500)
        
        # Gráficos de barras
        st.subheader("📊 Gráficos de Datos Climáticos")
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        axes = axes.flatten()
        
        variables = [
            ('radiacion_solar', 'Radiación Solar (MJ/m²/día)', 'yellow'),
            ('precipitacion', 'Precipitación (mm/día)', 'blue'),
            ('velocidad_viento', 'Velocidad del Viento (m/s)', 'green'),
            ('humedad_relativa', 'Humedad Relativa (%)', 'purple')
        ]
        
        for idx, (var, titulo, color) in enumerate(variables):
            axes[idx].bar([titulo], [datos[var]], color=color, edgecolor='black')
            axes[idx].set_ylabel(titulo)
            axes[idx].set_title(titulo)
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Recomendaciones climáticas
        st.subheader("🌦️ Recomendaciones Climáticas")
        
        if datos['precipitacion'] < 4:
            st.error("🚨 **SEQUÍA**: Precipitación insuficiente")
            st.markdown("""
            - Implementar sistema de riego
            - Usar mulch para conservar humedad
            - Seleccionar variedades resistentes a sequía
            - Reducir densidad de siembra
            """)
        elif datos['precipitacion'] > 10:
            st.warning("⚠️ **EXCESO DE LLUVIA**: Riesgo de encharcamiento")
            st.markdown("""
            - Mejorar drenaje del suelo
            - Control de enfermedades fúngicas
            - Aplicar fertilización foliar
            - Monitorear plagas
            """)
        
        if datos['radiacion_solar'] > 22:
            st.warning("⚠️ **ALTA RADIACIÓN**: Riesgo de estrés térmico")
            st.markdown("""
            - Implementar sombreado
            - Riego en horas frescas
            - Uso de protectores solares para plantas
            - Seleccionar variedades tolerantes al calor
            """)
    else:
        st.warning("No hay datos climáticos disponibles.")

# ============================================================================
# INTERFAZ PRINCIPAL
# ============================================================================
def main():
    # Inicializar session_state
    if 'gdf_original' not in st.session_state:
        st.session_state.gdf_original = None
    if 'gdf_analisis' not in st.session_state:
        st.session_state.gdf_analisis = None
    if 'analisis_textura' not in st.session_state:
        st.session_state.analisis_textura = None
    if 'area_total' not in st.session_state:
        st.session_state.area_total = 0.0
    if 'analisis_completado' not in st.session_state:
        st.session_state.analisis_completado = False
    if 'datos_clima' not in st.session_state:
        st.session_state.datos_clima = {}
    if 'datos_satelitales' not in st.session_state:
        st.session_state.datos_satelitales = {}
    if 'datos_clima_historicos' not in st.session_state:
        st.session_state.datos_clima_historicos = {}
    
    uploaded_file = st.file_uploader("📤 Suba su archivo de parcela (Shapefile ZIP o KML)", type=["zip", "kml"])
    
    if uploaded_file is not None:
        with st.spinner("🔄 Procesando archivo geoespacial..."):
            gdf = procesar_archivo(uploaded_file)
            if gdf is not None:
                st.session_state.gdf_original = gdf
                st.success("✅ Archivo procesado exitosamente")
    
    if st.session_state.gdf_original is not None:
        st.markdown("### 🗺️ Vista previa de la parcela")
        area_total = calcular_superficie(st.session_state.gdf_original)
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
        
        mapa_parcela = crear_mapa_visualizador_parcela(st.session_state.gdf_original)
        if mapa_parcela:
            st_folium(mapa_parcela, width=800, height=500)
        
        st.markdown("### ⚙️ Parámetros del análisis")
        col1, col2, col3 = st.columns(3)
        with col1:
            cultivo = st.selectbox("🌱 Seleccione el cultivo", ["PALMA_ACEITERA", "CACAO", "BANANO"], key="cultivo")
        with col2:
            mes_analisis = st.selectbox("📅 Mes de análisis", list(FACTORES_MES.keys()), key="mes_analisis")
        with col3:
            n_zonas = st.slider("🔢 Número de zonas para análisis", 1, 100, 16, key="n_zonas")
        
        analisis_tipo = st.selectbox("🔍 Tipo de Análisis:", 
                                   ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK", "ANÁLISIS DE TEXTURA"],
                                   key="analisis_tipo")
        
        nutriente = st.selectbox("Nutriente:", 
                               ["NITRÓGENO", "FÓSFORO", "POTASIO"],
                               key="nutriente")
        
        if st.button("🔍 Iniciar Análisis", type="primary"):
            with st.spinner("🔬 Analizando parcela con datos históricos de NASA POWER..."):
                gdf_zonas = dividir_parcela_en_zonas(st.session_state.gdf_original, n_zonas)
                gdf_zonas = gdf_zonas.reset_index(drop=True)
                gdf_zonas['id_zona'] = range(1, len(gdf_zonas) + 1)
                
                centroid_total = gdf_zonas.unary_union.centroid
                
                # Datos históricos
                datos_historicos = obtener_datos_nasa_power_historicos(centroid_total.y, centroid_total.x, years=10)
                st.session_state.datos_clima_historicos = datos_historicos
                
                # Análisis de textura
                gdf_textura = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                st.session_state.analisis_textura = gdf_textura
                
                # Datos climáticos actuales
                datos_clima = obtener_datos_nasa_power(centroid_total.y, centroid_total.x, mes_analisis)
                st.session_state.datos_clima = datos_clima
                
                # Datos satelitales
                fecha_analisis = datetime(datetime.now().year, list(FACTORES_MES.keys()).index(mes_analisis) + 1, 15)
                datos_satelitales = obtener_datos_satelitales(centroid_total.y, centroid_total.x, fecha_analisis, cultivo)
                st.session_state.datos_satelitales = datos_satelitales
                
                # Análisis de fertilidad
                gdf_fertilidad = calcular_indices_gee(
                    gdf_zonas, cultivo, mes_analisis, analisis_tipo, nutriente,
                    ndvi_base=datos_satelitales['ndvi'],
                    evi_base=datos_satelitales['evi']
                )
                
                # Potencial de cosecha (solo para palma)
                if cultivo == "PALMA_ACEITERA":
                    gdf_fertilidad = calcular_potencial_cosecha(gdf_fertilidad, datos_clima, datos_satelitales, cultivo)
                
                st.session_state.gdf_analisis = gdf_fertilidad
                st.session_state.area_total = area_total
                st.session_state.analisis_completado = True
                
                st.success("✅ Análisis completado con éxito")
    
    if st.session_state.analisis_completado:
        st.markdown("### 📊 Seleccione el tipo de análisis a visualizar")
        opcion = st.selectbox("🔍 Tipo de análisis",
                            ["ANÁLISIS PRINCIPAL (Fertilidad)",
                             "ANÁLISIS DE TEXTURA",
                             "POTENCIAL DE COSECHA (Palma)",
                             "ANÁLISIS CLIMÁTICO (NASA POWER)",
                             "MAPAS CLIMÁTICOS HISTÓRICOS"],
                            key="tipo_analisis")
        
        if opcion == "ANÁLISIS PRINCIPAL (Fertilidad)":
            mostrar_resultados_principales()
        elif opcion == "ANÁLISIS DE TEXTURA":
            mostrar_resultados_textura()
        elif opcion == "POTENCIAL DE COSECHA (Palma)":
            mostrar_potencial_cosecha()
        elif opcion == "ANÁLISIS CLIMÁTICO (NASA POWER)":
            mostrar_clima_detalles()
        elif opcion == "MAPAS CLIMÁTICOS HISTÓRICOS":
            mostrar_mapas_climaticos_historicos()

# ============================================================================
# EJECUCIÓN
# ============================================================================
if __name__ == "__main__":
    main()
