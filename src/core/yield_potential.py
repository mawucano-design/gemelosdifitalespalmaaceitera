import numpy as np

def calcular_potencial_cosecha(gdf_analisis, datos_clima, cultivo="PALMA_ACEITERA"):
    """
    Calcula el potencial de cosecha usando datos climáticos y de suelo.
    """
    if cultivo != "PALMA_ACEITERA":
        return gdf_analisis  # Solo para palma por ahora
    
    # Promedios mensuales
    rad_solar = datos_clima['radiacion_solar']
    precip_mensual = datos_clima['precipitacion'] * 30  # mm/mes
    viento = datos_clima['velocidad_viento']
    
    # Factores de limitación
    factor_rad = min(1.0, rad_solar / 20.0) if rad_solar else 0.5
    factor_agua = min(1.0, precip_mensual / 200.0) if precip_mensual else 0.3
    factor_viento = max(0.7, 1.0 - (viento - 2.0) / 10.0) if viento else 0.9
    
    # Añadir columnas al GeoDataFrame
    gdf_analisis['radiacion_solar'] = rad_solar
    gdf_analisis['precipitacion_mm_mes'] = precip_mensual
    gdf_analisis['velocidad_viento'] = viento
    gdf_analisis['factor_radiacion'] = factor_rad
    gdf_analisis['factor_agua'] = factor_agua
    gdf_analisis['factor_viento'] = factor_viento
    
    # Potencial de cosecha (ton/ha/año)
    potencial_base = 25.0  # máximo teórico
    gdf_analisis['potencial_cosecha'] = (
        potencial_base * 
        gdf_analisis['indice_fertilidad'] * 
        factor_rad * 
        factor_agua * 
        factor_viento
    )
    
    return gdf_analisis
