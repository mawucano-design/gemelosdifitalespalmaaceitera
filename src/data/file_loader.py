import geopandas as gpd
import numpy as np
import os
import tempfile
import zipfile
from shapely.geometry import Polygon
import fiona

# ✅ Habilitar soporte para KML en Fiona
fiona.drvsupport.supported_drivers['KML'] = 'rw'

def calcular_superficie(gdf):
    """Calcula superficie en hectáreas con manejo robusto de CRS"""
    try:
        if gdf.empty or gdf.geometry.isnull().all():
            return gdf.assign(area_ha=0.0)['area_ha']
        if gdf.crs and gdf.crs.is_geographic:
            try:
                gdf_proj = gdf.to_crs('EPSG:3116')
                area_m2 = gdf_proj.geometry.area
            except:
                area_m2 = gdf.geometry.area * 111000 * 111000
        else:
            area_m2 = gdf.geometry.area
        area_ha = area_m2 / 10000
        return area_ha
    except:
        return gdf.assign(area_ha=1.0)['area_ha']

def procesar_archivo(uploaded_file):
    """Procesa ZIP con shapefile o archivo KML usando Fiona con soporte KML"""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            if uploaded_file.name.lower().endswith('.kml'):
                # ✅ Cargar KML con Fiona (habilitado arriba)
                gdf = gpd.read_file(file_path, driver='KML')
            else:
                # ZIP con shapefile
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                else:
                    return None

            if not gdf.is_valid.all():
                gdf = gdf.make_valid()
            return gdf
    except Exception as e:
        return None
