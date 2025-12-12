import os
import requests
import geopandas as gpd
from datetime import datetime, timedelta
import rasterio
from rasterio.plot import show
import numpy as np
import tempfile
import streamlit as st

class PlanetScopeLoader:
    """Descarga y procesa imágenes PlanetScope para análisis agrícola"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('PLANET_API_KEY')
        self.base_url = "https://api.planet.com/basemaps/v1/mosaics"
        
    def search_imagery(self, geometry, start_date=None, end_date=None, 
                       cloud_cover=0.1, item_types=['PSScene']):
        """
        Busca imágenes PlanetScope disponibles para un área
        
        Args:
            geometry: GeoJSON geometry del área de interés
            start_date: Fecha inicio (str 'YYYY-MM-DD')
            end_date: Fecha fin (str 'YYYY-MM-DD')
            cloud_cover: Máximo % nubes permitido
            item_types: Tipos de imágenes ['PSScene', 'REOrthoTile']
            
        Returns:
            Lista de imágenes disponibles
        """
        
        # Configurar fechas por defecto (últimos 30 días)
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Crear filtro de búsqueda
        search_filter = {
            "type": "AndFilter",
            "config": [
                {
                    "type": "GeometryFilter",
                    "field_name": "geometry",
                    "config": geometry
                },
                {
                    "type": "DateRangeFilter",
                    "field_name": "acquired",
                    "config": {
                        "gte": start_date,
                        "lte": end_date
                    }
                },
                {
                    "type": "RangeFilter",
                    "field_name": "cloud_cover",
                    "config": {
                        "lte": cloud_cover
                    }
                },
                {
                    "type": "AssetFilter",
                    "config": ["visual", "analytic"]
                }
            ]
        }
        
        search_endpoint = "https://api.planet.com/data/v1/quick-search"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'api-key {self.api_key}'
        }
        
        for item_type in item_types:
            search_request = {
                "item_types": [item_type],
                "filter": search_filter
            }
            
            try:
                response = requests.post(
                    search_endpoint,
                    json=search_request,
                    headers=headers
                )
                
                if response.status_code == 200:
                    results = response.json()
                    if results['features']:
                        return self._process_search_results(results)
                        
            except Exception as e:
                st.warning(f"Error buscando {item_type}: {str(e)}")
                
        return []
    
    def _process_search_results(self, results):
        """Procesa resultados de búsqueda de Planet"""
        processed = []
        
        for feature in results['features']:
            item = {
                'id': feature['id'],
                'date': feature['properties']['acquired'],
                'cloud_cover': feature['properties'].get('cloud_cover', 0),
                'resolution': feature['properties'].get('ground_sample_distance', 3),
                'instrument': feature['properties'].get('instrument', 'PlanetScope'),
                'geometry': feature['geometry'],
                'assets': feature.get('_links', {}).get('assets', {})
            }
            processed.append(item)
            
        return processed
    
    def download_image(self, item_id, geometry, output_dir='./data/planet', 
                       asset_type='visual', bbox=None):
        """
        Descarga una imagen PlanetScope específica
        
        Args:
            item_id: ID de la imagen Planet
            geometry: GeoJSON del área de recorte
            output_dir: Directorio de salida
            asset_type: Tipo de asset ('visual', 'analytic', 'udm')
            bbox: Bounding box [minx, miny, maxx, maxy] para recortar
            
        Returns:
            Ruta al archivo descargado
        """
        
        # Crear directorio si no existe
        os.makedirs(output_dir, exist_ok=True)
        
        # Endpoint para descarga
        download_url = f"https://api.planet.com/data/v1/item-types/PSScene/items/{item_id}/assets"
        
        headers = {
            'Authorization': f'api-key {self.api_key}'
        }
        
        try:
            # 1. Obtener assets disponibles
            response = requests.get(download_url, headers=headers)
            
            if response.status_code != 200:
                st.error(f"Error obteniendo assets: {response.status_code}")
                return None
                
            assets = response.json()
            
            if asset_type not in assets:
                st.error(f"Asset {asset_type} no disponible")
                return None
                
            # 2. Activar el asset
            activation_url = assets[asset_type]['_links']['activate']
            activate_resp = requests.get(activation_url, headers=headers)
            
            if activate_resp.status_code != 200:
                # Intentar activar
                activate_resp = requests.post(activation_url, headers=headers)
                
            # 3. Esperar activación (simplificado - en producción usar polling)
            import time
            time.sleep(2)
            
            # 4. Descargar con recorte si hay bbox
            download_link = assets[asset_type]['_links']['_self']
            
            if bbox:
                # Descargar recortado
                clip_url = f"{download_link}/clip?aoi={geometry}"
                clip_response = requests.get(clip_url, headers=headers)
                
                if clip_response.status_code == 200:
                    output_path = os.path.join(output_dir, f"{item_id}_{asset_type}_clip.tif")
                    with open(output_path, 'wb') as f:
                        f.write(clip_response.content)
                    return output_path
                    
            # 5. Descarga completa (simplificada para demo)
            # EN PRODUCCIÓN: Aquí iría la lógica real de descarga
            st.info(f"En producción, se descargaría: {item_id}")
            
            # Para demo, crear una imagen sintética
            return self._create_demo_image(geometry, output_dir, item_id)
            
        except Exception as e:
            st.error(f"Error descargando imagen: {str(e)}")
            return None
    
    def _create_demo_image(self, geometry, output_dir, item_id):
        """Crea una imagen de demostración (para desarrollo)"""
        from PIL import Image, ImageDraw
        import random
        
        # Crear imagen sintética de 1000x1000 píxeles
        img_size = (1000, 1000)
        img = Image.new('RGB', img_size, (100, 150, 100))  # Fondo verde
        
        draw = ImageDraw.Draw(img)
        
        # Simular patrones de cultivo
        for _ in range(50):
            x = random.randint(100, 900)
            y = random.randint(100, 900)
            radius = random.randint(20, 40)
            
            # Árboles como círculos
            color = (
                random.randint(80, 120),   # R
                random.randint(130, 180),  # G
                random.randint(80, 120)    # B
            )
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], 
                        fill=color, outline=(60, 100, 60))
        
        # Guardar imagen
        output_path = os.path.join(output_dir, f"{item_id}_demo.png")
        img.save(output_path)
        
        return output_path
    
    def calculate_vegetation_indices(self, image_path):
        """
        Calcula índices de vegetación a partir de imagen PlanetScope
        
        Args:
            image_path: Ruta a la imagen (TIFF con bandas)
            
        Returns:
            Diccionario con índices NDVI, NDWI, GNDVI
        """
        
        try:
            with rasterio.open(image_path) as src:
                # Leer bandas (asumiendo orden RGBI para PlanetScope)
                red = src.read(1).astype(float)
                green = src.read(2).astype(float)
                blue = src.read(3).astype(float)
                nir = src.read(4).astype(float) if src.count >= 4 else None
                
                # Calcular índices
                indices = {}
                
                if nir is not None:
                    # NDVI
                    ndvi = (nir - red) / (nir + red + 1e-10)
                    indices['ndvi'] = {
                        'mean': float(np.nanmean(ndvi)),
                        'min': float(np.nanmin(ndvi)),
                        'max': float(np.nanmax(ndvi)),
                        'std': float(np.nanstd(ndvi))
                    }
                    
                    # GNDVI (Green NDVI)
                    gndvi = (nir - green) / (nir + green + 1e-10)
                    indices['gndvi'] = {
                        'mean': float(np.nanmean(gndvi)),
                        'min': float(np.nanmin(gndvi)),
                        'max': float(np.nanmax(gndvi)),
                        'std': float(np.nanstd(gndvi))
                    }
                    
                    # NDWI (Water Index)
                    ndwi = (green - nir) / (green + nir + 1e-10)
                    indices['ndwi'] = {
                        'mean': float(np.nanmean(ndwi)),
                        'min': float(np.nanmin(ndwi)),
                        'max': float(np.nanmax(ndwi)),
                        'std': float(np.nanstd(ndwi))
                    }
                
                return indices
                
        except Exception as e:
            st.warning(f"No se pudieron calcular índices: {str(e)}")
            # Retornar valores de demostración
            return {
                'ndvi': {'mean': 0.65, 'min': 0.3, 'max': 0.85, 'std': 0.1},
                'gndvi': {'mean': 0.55, 'min': 0.25, 'max': 0.75, 'std': 0.08},
                'ndwi': {'mean': 0.15, 'min': -0.1, 'max': 0.4, 'std': 0.05}
            }

def test_planet_connection():
    """Función de prueba para conexión con Planet"""
    loader = PlanetScopeLoader()
    
    # Crear geometría de ejemplo (Bogotá, Colombia)
    example_geom = {
        "type": "Polygon",
        "coordinates": [[
            [-74.2, 4.5],
            [-74.0, 4.5],
            [-74.0, 4.7],
            [-74.2, 4.7],
            [-74.2, 4.5]
        ]]
    }
    
    st.info("🔍 Buscando imágenes PlanetScope disponibles...")
    images = loader.search_imagery(example_geom)
    
    if images:
        st.success(f"✅ Encontradas {len(images)} imágenes")
        for img in images[:3]:  # Mostrar primeras 3
            st.write(f"- {img['date']}: {img['id']} (Nubes: {img['cloud_cover']*100:.1f}%)")
    else:
        st.warning("No se encontraron imágenes. Usando modo demostración.")
        
    return loader
