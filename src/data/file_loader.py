import geopandas as gpd
import numpy as np
import os
import tempfile
import zipfile
from shapely.geometry import shape
import fiona
from fastkml import kml
from fastkml.geometry import Geometry

def procesar_archivo(uploaded_file):
    """Procesa ZIP con shapefile o archivo KML usando fastkml como fallback"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            if uploaded_file.name.lower().endswith('.kml'):
                # Usar fastkml para KML
                with open(file_path, 'rb') as f:
                    doc = f.read()
                k = kml.KML()
                k.from_string(doc)
                geometries = []
                for feature in k.features():
                    if hasattr(feature, 'geometry') and feature.geometry:
                        geom = shape(feature.geometry)
                        if not geom.is_empty:
                            geometries.append(geom)
                if geometries:
                    gdf = gpd.GeoDataFrame(geometry=geometries, crs="EPSG:4326")
                    return gdf
                else:
                    return None
            else:
                # ZIP con shapefile
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    return gdf
                else:
                    return None
    except Exception as e:
        return None
