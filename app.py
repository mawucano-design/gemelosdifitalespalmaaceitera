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
import random
import cv2
from PIL import Image
import requests
import rasterio
from rasterio.plot import show

# ============================================================================
# CONFIGURACIÓN DE LA PÁGINA DE STREAMLIT
# ============================================================================
st.set_page_config(page_title="🌴 Gemelo Digital Plantaciones", layout="wide")
st.title("🌱 GEMELO DIGITAL PLANTACIONES - VISIÓN ARTIFICIAL + GEE + AGROECOLOGÍA")
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

# PARÁMETROS DE TEXTURA DEL SUELO POR CULTIVO - NOMBRES ACTUALIZADOS
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

# CLASIFICACIÓN DE TEXTURAS DEL SUELO - NOMBRES ACTUALIZADOS
CLASIFICACION_TEXTURAS = {
    'Arenoso': {'arena_min': 85, 'arena_max': 100, 'limo_max': 15, 'arcilla_max': 15},
    'Franco Arcilloso-Arenoso': {'arena_min': 70, 'arena_max': 85, 'limo_max': 30, 'arcilla_max': 20},
    'Franco': {'arena_min': 43, 'arena_max': 52, 'limo_min': 28, 'limo_max': 50, 'arcilla_min': 7, 'arcilla_max': 27},
    'Franco Arcilloso': {'arena_min': 20, 'arena_max': 45, 'limo_min': 15, 'limo_max': 53, 'arcilla_min': 27, 'arcilla_max': 40},
    'Arcilloso': {'arena_max': 45, 'limo_max': 40, 'arcilla_min': 40}
}

# FACTORES EDÁFICOS MÁS REALISTAS - NOMBRES ACTUALIZADOS
FACTORES_SUELO = {
    'Arcilloso': {'retention': 1.3, 'drainage': 0.7, 'aeration': 0.6, 'workability': 0.5},
    'Franco Arcilloso': {'retention': 1.2, 'drainage': 0.8, 'aeration': 0.7, 'workability': 0.7},
    'Franco': {'retention': 1.0, 'drainage': 1.0, 'aeration': 1.0, 'workability': 1.0},
    'Franco Arcilloso-Arenoso': {'retention': 0.8, 'drainage': 1.2, 'aeration': 1.3, 'workability': 1.2},
    'Arenoso': {'retention': 0.6, 'drainage': 1.4, 'aeration': 1.5, 'workability': 1.4}
}

# RECOMENDACIONES POR TIPO DE TEXTURA - NOMBRES ACTUALIZADOS
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

# PRINCIPIOS AGROECOLÓGICOS - RECOMENDACIONES ESPECÍFICAS
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
    "MAYO": 1.15, "JUNIO": 1.1, "JULio": 1.05, "AGOSTO": 1.0,
    "SEPTIEMBRE": 1.0, "OCTUBRE": 1.05, "NOVIEMBRE": 1.1, "DICIEMBRE": 1.05
}

FACTORES_K_MES = {
    "ENERO": 1.0, "FEBRERO": 1.0, "MARZO": 1.0, "ABRIL": 1.05,
    "MAYO": 1.1, "JUNIO": 1.15, "JULIO": 1.2, "AGOSTO": 1.15,
    "SEPTIEMBRE": 1.1, "OCTUBRE": 1.05, "NOVIEMBRE": 1.0, "DICIEMBRE": 1.0
}

# PALETAS GEE MEJORADAS
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#01665e'],
    'FOSFORO': ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
    'POTASIO': ['#4d004b', '#810f7c', '#8c6bb1', '#8c96c6', '#9ebcda', '#bfd3e6', '#e0ecf4', '#edf8fb'],
    'TEXTURA': ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e']
}

# ============================================================================
# INICIALIZACIÓN DE SESSION_STATE
# ============================================================================
if 'analisis_completado' not in st.session_state:
    st.session_state.analisis_completado = False
if 'gdf_analisis' not in st.session_state:
    st.session_state.gdf_analisis = None
if 'gdf_original' not in st.session_state:
    st.session_state.gdf_original = None
if 'gdf_zonas' not in st.session_state:
    st.session_state.gdf_zonas = None
if 'area_total' not in st.session_state:
    st.session_state.area_total = 0
if 'datos_demo' not in st.session_state:
    st.session_state.datos_demo = False
if 'analisis_textura' not in st.session_state:
    st.session_state.analisis_textura = None
if 'digital_twin' not in st.session_state:
    st.session_state.digital_twin = None
if 'trees_gdf' not in st.session_state:
    st.session_state.trees_gdf = None
if 'tree_recommendations' not in st.session_state:
    st.session_state.tree_recommendations = None
if 'planet_images' not in st.session_state:
    st.session_state.planet_images = None
if 'vision_detections' not in st.session_state:
    st.session_state.vision_detections = None

# ============================================================================
# MÓDULO PLANETSCOPE LOADER (INTEGRADO)
# ============================================================================
class PlanetScopeLoader:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('PLANET_API_KEY', 'demo_key')
        self.base_url = "https://api.planet.com/basemaps/v1/mosaics"
    
    def search_imagery(self, geometry, start_date=None, end_date=None, cloud_cover=0.1):
        """Busca imágenes PlanetScope disponibles"""
        try:
            st.info("🔍 Buscando imágenes PlanetScope... (Modo Demo)")
            
            # Para demo, crear resultados simulados
            demo_results = [
                {
                    'id': f'PSScene_20250115_{i:04d}',
                    'date': f'2025-01-{15+i:02d}',
                    'cloud_cover': random.uniform(0.05, 0.15),
                    'resolution': 3.0,
                    'instrument': 'PlanetScope',
                    'thumbnail_url': None
                }
                for i in range(3)
            ]
            
            st.success(f"✅ Encontradas {len(demo_results)} imágenes")
            return demo_results
            
        except Exception as e:
            st.warning(f"⚠️ Error en búsqueda: {str(e)}")
            return []
    
    def download_image(self, item_id, geometry, output_dir='./data/planet', asset_type='visual'):
        """Descarga imagen PlanetScope (demo)"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # Crear imagen de demostración
            from PIL import Image, ImageDraw
            import random
            
            img_size = (1000, 1000)
            img = Image.new('RGB', img_size, (100, 150, 100))
            draw = ImageDraw.Draw(img)
            
            # Simular árboles
            for _ in range(50):
                x = random.randint(100, 900)
                y = random.randint(100, 900)
                radius = random.randint(20, 40)
                color = (random.randint(80, 120), random.randint(130, 180), random.randint(80, 120))
                draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=color)
            
            output_path = os.path.join(output_dir, f"{item_id}_demo.png")
            img.save(output_path)
            
            return output_path
            
        except Exception as e:
            st.error(f"❌ Error descargando: {str(e)}")
            return None

# ============================================================================
# MÓDULO VISIÓN ARTIFICIAL (INTEGRADO)
# ============================================================================
class VisionAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('ROBOFLOW_API_KEY', 'demo_key')
    
    def detect_palm_trees(self, image_path, confidence=0.5):
        """Detecta palmeras en imagen (demo)"""
        try:
            st.info("🌴 Detectando palmeras con Visión Artificial...")
            
            # Simular detecciones
            img = Image.open(image_path)
            width, height = img.size
            
            detections = []
            num_trees = random.randint(30, 60)
            
            for i in range(num_trees):
                detections.append({
                    'class': 'palm_tree',
                    'confidence': random.uniform(0.7, 0.95),
                    'bbox': {
                        'x': random.randint(50, width-50),
                        'y': random.randint(50, height-50),
                        'width': random.randint(30, 80),
                        'height': random.randint(40, 100)
                    },
                    'is_demo': True
                })
            
            st.success(f"✅ Detectadas {len(detections)} palmeras")
            return detections
            
        except Exception as e:
            st.error(f"❌ Error en detección: {str(e)}")
            return []
    
    def create_visualization(self, image_path, detections):
        """Crea visualización con bounding boxes"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                img = np.array(Image.open(image_path).convert('RGB'))
            
            for det in detections:
                x = int(det['bbox']['x'])
                y = int(det['bbox']['y'])
                w = int(det['bbox']['width'])
                h = int(det['bbox']['height'])
                
                # Dibujar bounding box
                cv2.rectangle(img, (x-w//2, y-h//2), (x+w//2, y+h//2), (0, 255, 0), 2)
                
                # Etiqueta
                label = f"Palma {det['confidence']:.1%}"
                cv2.putText(img, label, (x-w//2, y-h//2-5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Guardar resultado
            output_path = tempfile.mktemp(suffix='.jpg')
            cv2.imwrite(output_path, img)
            return output_path
            
        except Exception as e:
            st.error(f"Error visualización: {str(e)}")
            return None

# ============================================================================
# MÓDULO GEMELO DIGITAL (INTEGRADO)
# ============================================================================
class DigitalTwinBuilder:
    def __init__(self):
        self.trees_gdf = None
        
    def create_from_detections(self, detections, bounds):
        """Crea gemelo digital a partir de detecciones"""
        try:
            trees_data = []
            
            for i, det in enumerate(detections):
                # Convertir coordenadas de píxeles a geográficas (simplificado)
                xmin, ymin, xmax, ymax = bounds
                lon = xmin + (det['bbox']['x'] / 1000) * (xmax - xmin)
                lat = ymin + (det['bbox']['y'] / 1000) * (ymax - ymin)
                
                # Salud aleatoria
                health_score = random.uniform(0.3, 0.9)
                health_status = "EXCELENTE" if health_score > 0.8 else "BUENA" if health_score > 0.6 else "MODERADA" if health_score > 0.4 else "CRÍTICA"
                
                trees_data.append({
                    'tree_id': f"PALMA_{i:04d}",
                    'species': 'Elaeis guineensis',
                    'health_score': health_score,
                    'health_status': health_status,
                    'confidence': det['confidence'],
                    'age_estimate': random.randint(3, 12),
                    'geometry': Point(lon, lat)
                })
            
            self.trees_gdf = gpd.GeoDataFrame(trees_data, crs="EPSG:4326")
            return self.trees_gdf
            
        except Exception as e:
            st.error(f"Error creando gemelo: {str(e)}")
            return None

# ============================================================================
# FUNCIONES AUXILIARES EXISTENTES
# ============================================================================
def clasificar_textura_suelo(arena, limo, arcilla):
    """Clasifica la textura del suelo según USDA"""
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
            
    except Exception as e:
        return "NO_DETERMINADA"

def calcular_superficie(geom):
    """Calcula superficie en hectáreas para una geometría individual (Polygon/MultiPolygon)"""
    try:
        if geom is None or geom.is_empty:
            return 0.0
        
        # Crear un GeoDataFrame temporal con una sola fila para facilitar la transformación
        gdf_temp = gpd.GeoDataFrame({'geometry': [geom]}, crs='EPSG:4326')
        
        # Si la geometría está en grados (coordenadas geográficas), proyectar a metros
        if gdf_temp.crs.is_geographic:
            try:
                # Proyección UTM para Colombia (ajustar según zona)
                gdf_proj = gdf_temp.to_crs('EPSG:3116')  # MAGNA-SIRGAS / Colombia West zone
                area_m2 = gdf_proj.geometry.area.iloc[0]
            except Exception as proj_error:
                # Fallback: aproximación simple (1 grado ≈ 111,111 metros)
                area_m2 = geom.area * 111111 * 111111
        else:
            # Asumir que ya está en un sistema proyectado (metros)
            area_m2 = geom.area
        
        # Convertir metros cuadrados a hectáreas
        area_ha = area_m2 / 10000.0
        return float(area_ha)
        
    except Exception as e:
        # Fallback en caso de cualquier error
        try:
            return float(geom.area / 10000.0)
        except:
            return 1.0  # Valor por defecto seguro

def dividir_parcela_en_zonas(gdf, n_zonas):
    """Divide la parcela en zonas de manejo"""
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
        
        sub_poligonos = []
        n_cols = math.ceil(math.sqrt(n_zonas))
        n_rows = math.ceil(n_zonas / n_cols)
        
        width = (maxx - minx) / n_cols
        height = (maxy - miny) / n_rows
        
        for i in range(n_rows):
            for j in range(n_cols):
                if len(sub_poligonos) >= n_zonas:
                    break
                    
                cell_poly = Polygon([
                    (minx + j * width, miny + i * height),
                    (minx + (j + 1) * width, miny + i * height),
                    (minx + (j + 1) * width, miny + (i + 1) * height),
                    (minx + j * width, miny + (i + 1) * height)
                ])
                
                if cell_poly.is_valid:
                    intersection = parcela_principal.intersection(cell_poly)
                    if not intersection.is_empty:
                        sub_poligonos.append(intersection)
        
        if sub_poligonos:
            nuevo_gdf = gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
            return nuevo_gdf
        else:
            return gdf
            
    except Exception as e:
        return gdf

def crear_mapa_interactivo(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    """Crea mapa interactivo con Folium"""
    centroid = gdf.geometry.centroid.iloc[0]
    
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=15,
        tiles='OpenStreetMap'
    )
    
    # Añadir otras capas
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite'
    ).add_to(m)
    
    if columna_valor and analisis_tipo:
        # Colorear según valor
        if analisis_tipo == "FERTILIDAD ACTUAL":
            vmin, vmax = 0, 1
            colores = PALETAS_GEE['FERTILIDAD']
        elif analisis_tipo == "ANÁLISIS DE TEXTURA":
            colores_textura = {
                'Arenoso': '#d8b365',
                'Franco Arcilloso-Arenoso': '#f6e8c3', 
                'Franco': '#c7eae5',
                'Franco Arcilloso': '#5ab4ac',
                'Arcilloso': '#01665e'
            }
        else:
            if nutriente == "NITRÓGENO":
                vmin, vmax = 0, 250
                colores = PALETAS_GEE['NITROGENO']
            elif nutriente == "FÓSFORO":
                vmin, vmax = 0, 120
                colores = PALETAS_GEE['FÓSFORO']
            else:
                vmin, vmax = 0, 200
                colores = PALETAS_GEE['POTASIO']
        
        for idx, row in gdf.iterrows():
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                textura = row[columna_valor]
                color = colores_textura.get(textura, '#999999')
            else:
                valor = row[columna_valor]
                valor_norm = (valor - vmin) / (vmax - vmin)
                valor_norm = max(0, min(1, valor_norm))
                color_idx = int(valor_norm * (len(colores) - 1))
                color = colores[color_idx]
            
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.7
                }
            ).add_to(m)
    else:
        for idx, row in gdf.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x: {
                    'fillColor': '#1f77b4',
                    'color': '#2ca02c',
                    'weight': 3,
                    'fillOpacity': 0.5
                }
            ).add_to(m)
    
    folium.LayerControl().add_to(m)
    return m

def crear_mapa_arboles(gdf_arboles, gdf_parcela=None):
    """Crea mapa interactivo de árboles individuales"""
    if gdf_arboles.empty:
        return None
    
    centroid = gdf_arboles.geometry.centroid.iloc[0]
    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=16)
    
    # Añadir árboles con colores según salud
    for _, arbol in gdf_arboles.iterrows():
        color_map = {
            'EXCELENTE': 'green',
            'BUENA': 'lightgreen',
            'MODERADA': 'orange',
            'CRÍTICA': 'red'
        }
        color = color_map.get(arbol['health_status'], 'blue')
        
        folium.CircleMarker(
            location=[arbol.geometry.y, arbol.geometry.x],
            radius=6,
            color=color,
            fill=True,
            fillColor=color,
            popup=f"🌴 {arbol['tree_id']}<br>🏥 {arbol['health_status']}<br>📊 {arbol['health_score']:.0%}"
        ).add_to(m)
    
    # Añadir límites de parcela si existen
    if gdf_parcela is not None:
        folium.GeoJson(
            gdf_parcela.__geo_interface__,
            style_function=lambda x: {
                'fillColor': 'blue',
                'color': 'blue',
                'weight': 2,
                'fillOpacity': 0.1
            }
        ).add_to(m)
    
    return m

# ============================================================================
# FUNCIONES DE ANÁLISIS EXISTENTES (SIMPLIFICADAS)
# ============================================================================
def analizar_textura_suelo(gdf, cultivo, mes_analisis):
    """Análisis de textura del suelo"""
    zonas_gdf = gdf.copy()
    params = TEXTURA_SUELO_OPTIMA[cultivo]
    
    zonas_gdf['area_ha'] = zonas_gdf.geometry.apply(lambda g: calcular_superficie(g))
    zonas_gdf['arena'] = np.random.normal(params['arena_optima'], 5, len(zonas_gdf))
    zonas_gdf['limo'] = np.random.normal(params['limo_optima'], 5, len(zonas_gdf))
    zonas_gdf['arcilla'] = 100 - zonas_gdf['arena'] - zonas_gdf['limo']
    
    zonas_gdf['textura_suelo'] = zonas_gdf.apply(
        lambda row: clasificar_textura_suelo(row['arena'], row['limo'], row['arcilla']), axis=1
    )
    
    return zonas_gdf

def calcular_indices_gee(gdf, cultivo, mes_analisis, analisis_tipo, nutriente):
    """Calcula índices GEE"""
    params = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    
    # Inicializar columnas
    zonas_gdf['area_ha'] = 0.0
    zonas_gdf['nitrogeno'] = 0.0
    zonas_gdf['fosforo'] = 0.0
    zonas_gdf['potasio'] = 0.0
    zonas_gdf['indice_fertilidad'] = 0.0
    zonas_gdf['categoria'] = "MEDIA"
    
    for idx, row in zonas_gdf.iterrows():
        zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(row.geometry)
        zonas_gdf.loc[idx, 'nitrogeno'] = np.random.normal(params['NITROGENO']['optimo'], 20)
        zonas_gdf.loc[idx, 'fosforo'] = np.random.normal(params['FOSFORO']['optimo'], 10)
        zonas_gdf.loc[idx, 'potasio'] = np.random.normal(params['POTASIO']['optimo'], 25)
        zonas_gdf.loc[idx, 'indice_fertilidad'] = np.random.uniform(0.3, 0.9)
        zonas_gdf.loc[idx, 'categoria'] = random.choice(["EXCELENTE", "ALTA", "MEDIA", "BAJA", "MUY BAJA"])
    
    return zonas_gdf

def procesar_archivo(uploaded_file):
    """Procesa archivo subido"""
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
                if shp_files:
                    gdf = gpd.read_file(os.path.join(tmp_dir, shp_files[0]))
                else:
                    st.error("No se encontró shapefile")
                    return None
            
            if not gdf.is_valid.all():
                gdf = gpd.make_valid(gdf)
            
            return gdf
            
    except Exception as e:
        st.error(f"Error procesando archivo: {str(e)}")
        return None

# ============================================================================
# INTERFACES DE LA APLICACIÓN
# ============================================================================
def mostrar_modo_demo():
    """Muestra interfaz de demostración"""
    st.markdown("### 🚀 Modo Demostración")
    st.info("""
    **Para usar la aplicación:**
    1. Sube un archivo ZIP con shapefile de tu parcela
    2. Selecciona cultivo y tipo de análisis
    3. Configura parámetros en el sidebar
    4. Ejecuta el análisis
    
    **O usa datos de demostración:**
    """)
    
    if st.button("🎯 Cargar Datos de Demostración", type="primary"):
        poligono_ejemplo = Polygon([
            [-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], [-74.1, 4.7], [-74.1, 4.6]
        ])
        
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo']},
            geometry=[poligono_ejemplo],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo
        st.session_state.datos_demo = True
        st.rerun()

def mostrar_configuracion_parcela():
    """Configuración de parcela"""
    gdf_original = st.session_state.gdf_original
    
    st.success("✅ Parcela cargada correctamente")
    
    area_total = calcular_superficie(gdf_original.iloc[0].geometry) * len(gdf_original)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
    with col2:
        st.metric("🔢 Polígonos", len(gdf_original))
    with col3:
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    
    # Mapa de parcela
    st.markdown("### 🗺️ Visualizador de Parcela")
    mapa_parcela = crear_mapa_interactivo(gdf_original, "Parcela")
    st_folium(mapa_parcela, width=800, height=400)
    
    # Botón para ejecutar análisis
    if st.button("🚀 Ejecutar Análisis Completo", type="primary"):
        with st.spinner("🔄 Dividiendo parcela..."):
            gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
            st.session_state.gdf_zonas = gdf_zonas
        
        with st.spinner("🔬 Realizando análisis..."):
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                gdf_analisis = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                st.session_state.analisis_textura = gdf_analisis
            else:
                gdf_analisis = calcular_indices_gee(gdf_zonas, cultivo, mes_analisis, analisis_tipo, nutriente)
                st.session_state.gdf_analisis = gdf_analisis
            
            st.session_state.area_total = area_total
            st.session_state.analisis_completado = True
        
        st.rerun()

def mostrar_resultados_principales():
    """Muestra resultados principales"""
    gdf_analisis = st.session_state.gdf_analisis
    
    st.markdown("## 📈 RESULTADOS DEL ANÁLISIS")
    
    if st.button("⬅️ Volver"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Estadísticas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Índice Fertilidad", f"{gdf_analisis['indice_fertilidad'].mean():.3f}")
    with col2:
        st.metric("🌿 Nitrógeno", f"{gdf_analisis['nitrogeno'].mean():.1f} kg/ha")
    with col3:
        st.metric("🧪 Fósforo", f"{gdf_analisis['fosforo'].mean():.1f} kg/ha")
    
    # Mapa
    st.markdown("### 🗺️ Mapa de Resultados")
    columna = 'indice_fertilidad' if analisis_tipo == "FERTILIDAD ACTUAL" else 'recomendacion_npk'
    mapa = crear_mapa_interactivo(gdf_analisis, "Resultados", columna, analisis_tipo, nutriente)
    st_folium(mapa, width=800, height=500)

def mostrar_resultados_textura():
    """Muestra resultados de textura"""
    gdf_textura = st.session_state.analisis_textura
    
    st.markdown("## 🏗️ ANÁLISIS DE TEXTURA")
    
    if st.button("⬅️ Volver"):
        st.session_state.analisis_completado = False
        st.rerun()
    
    # Estadísticas
    col1, col2, col3 = st.columns(3)
    with col1:
        textura_pred = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "N/A"
        st.metric("🏗️ Textura Predominante", textura_pred)
    with col2:
        st.metric("🏖️ Arena", f"{gdf_textura['arena'].mean():.1f}%")
    with col3:
        st.metric("🧱 Arcilla", f"{gdf_textura['arcilla'].mean():.1f}%")
    
    # Mapa
    st.markdown("### 🗺️ Mapa de Texturas")
    mapa = crear_mapa_interactivo(gdf_textura, "Texturas", 'textura_suelo', "ANÁLISIS DE TEXTURA")
    st_folium(mapa, width=800, height=500)

def mostrar_gemelo_digital():
    """Muestra interfaz del gemelo digital"""
    st.markdown("## 🌴 GEMELO DIGITAL DE PLANTACIÓN")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Crear Gemelo (Demo)", key="create_demo"):
            builder = DigitalTwinBuilder()
            
            # Crear detecciones demo
            if st.session_state.gdf_original is not None:
                bounds = st.session_state.gdf_original.total_bounds
                detections = [{'bbox': {'x': i*20, 'y': i*15, 'width': 50, 'height': 60}, 'confidence': 0.8} 
                            for i in range(100)]
                
                trees_gdf = builder.create_from_detections(detections, bounds)
                st.session_state.trees_gdf = trees_gdf
                st.session_state.digital_twin = builder
                st.rerun()
    
    with col2:
        uploaded_image = st.file_uploader("📷 Subir imagen drone/satélite", type=['jpg', 'png'])
        
        if uploaded_image and st.session_state.gdf_original is not None:
            if st.button("🤖 Analizar con Visión Artificial"):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    image_path = os.path.join(tmp_dir, uploaded_image.name)
                    with open(image_path, "wb") as f:
                        f.write(uploaded_image.getvalue())
                    
                    analyzer = VisionAnalyzer()
                    detections = analyzer.detect_palm_trees(image_path)
                    
                    if detections:
                        st.session_state.vision_detections = detections
                        
                        # Crear visualización
                        viz_path = analyzer.create_visualization(image_path, detections)
                        if viz_path:
                            st.image(viz_path, caption="Detecciones de Palmeras")
    
    with col3:
        if st.button("🛰️ Buscar PlanetScope"):
            if st.session_state.gdf_original is not None:
                loader = PlanetScopeLoader()
                parcela_geom = st.session_state.gdf_original.iloc[0].geometry.__geo_interface__
                images = loader.search_imagery(parcela_geom)
                
                if images:
                    st.session_state.planet_images = images
                    for img in images[:3]:
                        st.write(f"📅 {img['date']} - ☁️ {img['cloud_cover']:.1%}")
    
    # Mostrar gemelo digital si existe
    if st.session_state.trees_gdf is not None:
        trees_gdf = st.session_state.trees_gdf
        
        st.subheader("📊 ESTADO DEL GEMELO DIGITAL")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🌴 Árboles", len(trees_gdf))
        with col2:
            st.metric("🏥 Salud Prom.", f"{trees_gdf['health_score'].mean():.1%}")
        with col3:
            excelentes = (trees_gdf['health_status'] == 'EXCELENTE').sum()
            st.metric("⭐ Excelentes", excelentes)
        with col4:
            st.metric("📅 Edad Prom.", f"{trees_gdf['age_estimate'].mean():.1f} años")
        
        # Mapa de árboles
        st.subheader("🗺️ MAPA DE ÁRBOLES INDIVIDUALES")
        mapa_arboles = crear_mapa_arboles(trees_gdf, st.session_state.gdf_original)
        if mapa_arboles:
            st_folium(mapa_arboles, width=800, height=500)
        
        # Tabla detallada
        st.subheader("📋 DETALLES POR ÁRBOL")
        display_cols = ['tree_id', 'health_status', 'health_score', 'age_estimate', 'confidence']
        st.dataframe(trees_gdf[display_cols], use_container_width=True, height=300)

# ============================================================================
# SIDEBAR PRINCIPAL
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    
    cultivo = st.selectbox("Cultivo:", ["PALMA_ACEITERA", "CACAO", "BANANO"])
    
    analisis_tipo = st.selectbox("Tipo de Análisis:", 
                               ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK", "ANÁLISIS DE TEXTURA"])
    
    if analisis_tipo == "RECOMENDACIONES NPK":
        nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    else:
        nutriente = None
    
    mes_analisis = st.selectbox("Mes:", 
                               ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                                "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"])
    
    st.subheader("🎯 División de Parcela")
    n_divisiones = st.slider("Zonas de manejo:", 16, 32, 24)
    
    st.subheader("📤 Subir Parcela")
    uploaded_file = st.file_uploader("Subir shapefile (ZIP) o KML", type=['zip', 'kml'])
    
    # Configuración avanzada
    with st.expander("🛰️ CONFIGURACIÓN AVANZADA"):
        planet_key = st.text_input("Planet API Key", type="password")
        roboflow_key = st.text_input("Roboflow API Key", type="password")
        
        if planet_key:
            os.environ['PLANET_API_KEY'] = planet_key
        if roboflow_key:
            os.environ['ROBOFLOW_API_KEY'] = roboflow_key
    
    # Botón de reinicio
    if st.button("🔄 Reiniciar Todo"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ============================================================================
# LÓGICA PRINCIPAL
# ============================================================================
def main():
    # Procesar archivo subido
    if uploaded_file is not None and not st.session_state.analisis_completado:
        with st.spinner("🔄 Procesando archivo..."):
            gdf_original = procesar_archivo(uploaded_file)
            if gdf_original is not None:
                st.session_state.gdf_original = gdf_original
                st.session_state.datos_demo = False
    
    # Mostrar interfaz según estado
    if st.session_state.analisis_completado:
        # Crear pestañas
        if analisis_tipo == "ANÁLISIS DE TEXTURA":
            mostrar_resultados_textura()
        else:
            tab1, tab2, tab3 = st.tabs(["📊 Análisis Principal", "🏗️ Textura", "🌴 Gemelo Digital"])
            
            with tab1:
                mostrar_resultados_principales()
            
            with tab2:
                if st.session_state.analisis_textura is not None:
                    mostrar_resultados_textura()
                else:
                    st.info("Ejecuta análisis para ver datos de textura")
            
            with tab3:
                mostrar_gemelo_digital()
    
    elif st.session_state.gdf_original is not None:
        mostrar_configuracion_parcela()
    else:
        mostrar_modo_demo()

# ============================================================================
# EJECUCIÓN
# ============================================================================
if __name__ == "__main__":
    main()
