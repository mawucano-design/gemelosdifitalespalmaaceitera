import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
from datetime import datetime
import streamlit as st

class DigitalTwinBuilder:
    """Construye y gestiona el gemelo digital de la plantación"""
    
    def __init__(self, crs="EPSG:4326"):
        self.crs = crs
        self.trees_gdf = None
        self.plantation_boundary = None
        
    def create_from_detections(self, detections, image_bounds, image_crs="EPSG:3857"):
        """
        Crea gemelo digital a partir de detecciones de visión artificial
        
        Args:
            detections: Lista de detecciones de Roboflow
            image_bounds: (xmin, ymin, xmax, ymax) en coordenadas de imagen
            image_crs: Sistema de coordenadas de la imagen
            
        Returns:
            GeoDataFrame con árboles individuales
        """
        
        trees_data = []
        
        for i, det in enumerate(detections):
            # Generar ID único
            tree_id = f"PALMA_{datetime.now().strftime('%Y%m%d')}_{i:04d}"
            
            # Convertir coordenadas de píxeles a geográficas
            # Esto requiere georreferenciación real - simplificado para demo
            img_x = det['pixel_coords']['center_x']
            img_y = det['pixel_coords']['center_y']
            
            # Mapeo lineal simple (en producción usar transformación afín)
            lon = self._pixel_to_lon(img_x, image_bounds)
            lat = self._pixel_to_lat(img_y, image_bounds)
            
            # Crear geometría
            geometry = Point(lon, lat)
            
            # Datos del árbol
            tree_data = {
                'tree_id': tree_id,
                'detection_id': i,
                'species': 'Elaeis guineensis',  # Palma aceitera
                'detection_confidence': det['confidence'],
                'health_score': det.get('health', {}).get('score', 0.5),
                'health_status': det.get('health', {}).get('status', 'DESCONOCIDA'),
                'canopy_area_m2': det.get('health', {}).get('canopy_area', 0) * 0.0001,  # Convertir a m²
                'dominant_color': det.get('health', {}).get('dominant_color', 'N/A'),
                'age_estimate': np.random.randint(3, 15),  # Estimado en años
                'last_analysis': datetime.now().isoformat(),
                'geometry': geometry
            }
            
            trees_data.append(tree_data)
        
        # Crear GeoDataFrame
        self.trees_gdf = gpd.GeoDataFrame(trees_data, crs=self.crs)
        
        # Calcular métricas agregadas
        self._calculate_plantation_metrics()
        
        st.success(f"✅ Gemelo digital creado: {len(self.trees_gdf)} árboles individuales")
        return self.trees_gdf
    
    def _pixel_to_lon(self, pixel_x, bounds):
        """Convierte coordenada X de píxel a longitud"""
        xmin, _, xmax, _ = bounds
        return xmin + (pixel_x / 1000) * (xmax - xmin)  # Simplificado
    
    def _pixel_to_lat(self, pixel_y, bounds):
        """Convierte coordenada Y de píxel a latitud"""
        _, ymin, _, ymax = bounds
        return ymin + (pixel_y / 1000) * (ymax - ymin)  # Simplificado
    
    def _calculate_plantation_metrics(self):
        """Calcula métricas generales de la plantación"""
        
        if self.trees_gdf is None or len(self.trees_gdf) == 0:
            return
        
        self.plantation_metrics = {
            'total_trees': len(self.trees_gdf),
            'avg_health': self.trees_gdf['health_score'].mean(),
            'health_distribution': self.trees_gdf['health_status'].value_counts().to_dict(),
            'avg_age': self.trees_gdf['age_estimate'].mean(),
            'total_canopy_area': self.trees_gdf['canopy_area_m2'].sum(),
            'trees_per_ha': len(self.trees_gdf) / 10  # Asumiendo 10ha para demo
        }
    
    def enrich_with_soil_data(self, soil_gdf):
        """
        Enriquece los datos de árboles con información del suelo
        
        Args:
            soil_gdf: GeoDataFrame con análisis de suelo por zona
            
        Returns:
            GeoDataFrame enriquecido
        """
        
        if self.trees_gdf is None:
            st.warning("Primero crea el gemelo digital")
            return None
        
        # Realizar join espacial
        trees_with_soil = gpd.sjoin(
            self.trees_gdf, 
            soil_gdf[['geometry', 'indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio']],
            how='left',
            predicate='within'
        )
        
        # Renombrar columnas de suelo
        trees_with_soil = trees_with_soil.rename(columns={
            'indice_fertilidad': 'soil_fertility',
            'nitrogeno': 'soil_nitrogen',
            'fosforo': 'soil_phosphorus',
            'potasio': 'soil_potassium'
        })
        
        self.trees_gdf = trees_with_soil
        return self.trees_gdf
    
    def predict_yield(self, model_type="linear"):
        """
        Predice rendimiento por árbol basado en salud y suelo
        
        Args:
            model_type: Tipo de modelo ('linear', 'random_forest')
            
        Returns:
            GeoDataFrame con predicciones de rendimiento
        """
        
        if self.trees_gdf is None:
            return None
        
        # Modelo simplificado para demo
        # En producción usarías scikit-learn con datos históricos
        
        def calculate_yield(row):
            # Factores que afectan el rendimiento
            health_factor = row['health_score'] * 2.0  # 0-2
            soil_factor = row.get('soil_fertility', 0.5) * 1.5  # 0-1.5
            age_factor = min(row['age_estimate'] / 8.0, 1.2)  # Máximo a 8 años
            
            # Rendimiento base por árbol (kg/año)
            base_yield = 20.0  # kg/árbol/año
            
            # Calcular rendimiento estimado
            estimated_yield = base_yield * health_factor * soil_factor * age_factor
            
            # Variabilidad aleatoria (±20%)
            variability = np.random.uniform(0.8, 1.2)
            
            return estimated_yield * variability
        
        self.trees_gdf['estimated_yield_kg'] = self.trees_gdf.apply(calculate_yield, axis=1)
        
        # Clasificar productividad
        conditions = [
            self.trees_gdf['estimated_yield_kg'] >= 30,
            self.trees_gdf['estimated_yield_kg'] >= 20,
            self.trees_gdf['estimated_yield_kg'] >= 10,
            self.trees_gdf['estimated_yield_kg'] < 10
        ]
        
        choices = ['ALTA', 'MEDIA-ALTA', 'MEDIA', 'BAJA']
        
        self.trees_gdf['productivity_class'] = np.select(conditions, choices, default='MEDIA')
        
        st.success(f"📈 Rendimiento total estimado: {self.trees_gdf['estimated_yield_kg'].sum():.0f} kg")
        
        return self.trees_gdf
    
    def generate_maintenance_recommendations(self):
        """Genera recomendaciones de mantenimiento por árbol"""
        
        if self.trees_gdf is None:
            return None
        
        recommendations = []
        
        for _, tree in self.trees_gdf.iterrows():
            rec = {
                'tree_id': tree['tree_id'],
                'priority': 'MEDIA',
                'actions': [],
                'timeline': '1-3 meses'
            }
            
            # Basado en salud
            if tree['health_score'] < 0.3:
                rec['priority'] = 'URGENTE'
                rec['actions'].extend([
                    'Aplicar fertilizante NPK completo',
                    'Revisar sistema de riego',
                    'Controlar plagas inmediatamente'
                ])
                rec['timeline'] = 'INMEDIATO'
            
            elif tree['health_score'] < 0.5:
                rec['priority'] = 'ALTA'
                rec['actions'].extend([
                    'Aplicar fertilizante nitrogenado',
                    'Podar hojas secas',
                    'Monitorear semanalmente'
                ])
            
            # Basado en suelo
            if 'soil_fertility' in tree and tree['soil_fertility'] < 0.4:
                rec['actions'].append('Aplicar materia orgánica')
            
            # Basado en productividad
            if 'productivity_class' in tree and tree['productivity_class'] == 'BAJA':
                rec['actions'].append('Considerar reemplazo a mediano plazo')
            
            recommendations.append(rec)
        
        self.trees_gdf['recommendations'] = [rec['actions'] for rec in recommendations]
        self.trees_gdf['maintenance_priority'] = [rec['priority'] for rec in recommendations]
        
        return recommendations
    
    def export_to_geojson(self, output_path):
        """Exporta el gemelo digital a GeoJSON"""
        
        if self.trees_gdf is None:
            return None
        
        self.trees_gdf.to_file(output_path, driver='GeoJSON')
        return output_path

def create_demo_digital_twin():
    """Crea un gemelo digital de demostración"""
    
    builder = DigitalTwinBuilder()
    
    # Crear árboles simulados
    num_trees = 150
    trees_data = []
    
    # Área de ejemplo (Colombia)
    min_lon, max_lon = -74.1, -74.0
    min_lat, max_lat = 4.6, 4.7
    
    for i in range(num_trees):
        tree_id = f"PALMA_DEMO_{i:04d}"
        
        # Posición aleatoria
        lon = np.random.uniform(min_lon, max_lon)
        lat = np.random.uniform(min_lat, max_lat)
        
        # Salud aleatoria (sesgada hacia buena salud)
        health_score = np.random.beta(2, 1)  # Sesgo hacia valores altos
        health_status = (
            "EXCELENTE" if health_score > 0.7 else
            "BUENA" if health_score > 0.5 else
            "MODERADA" if health_score > 0.3 else "CRÍTICA"
        )
        
        tree_data = {
            'tree_id': tree_id,
            'species': 'Elaeis guineensis',
            'health_score': health_score,
            'health_status': health_status,
            'age_estimate': np.random.randint(2, 12),
            'geometry': Point(lon, lat),
            'last_analysis': datetime.now().isoformat()
        }
        
        trees_data.append(tree_data)
    
    builder.trees_gdf = gpd.GeoDataFrame(trees_data, crs="EPSG:4326")
    builder._calculate_plantation_metrics()
    
    return builder
