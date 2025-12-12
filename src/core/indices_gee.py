import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
from src.utils.constants import (
    PARAMETROS_CULTIVOS,
    FACTORES_MES,
    FACTORES_N_MES,
    FACTORES_P_MES,
    FACTORES_K_MES,
    PALETAS_GEE
)
from src.data.file_loader import calcular_superficie

def calcular_indices_gee(gdf, cultivo, mes_analisis, analisis_tipo, nutriente):
    """Calcula índices GEE mejorados con cálculos NPK más precisos"""
    params = PARAMETROS_CULTIVOS[cultivo]
    zonas_gdf = gdf.copy()
    # FACTORES ESTACIONALES MEJORADOS
    factor_mes = FACTORES_MES[mes_analisis]
    factor_n_mes = FACTORES_N_MES[mes_analisis]
    factor_p_mes = FACTORES_P_MES[mes_analisis]
    factor_k_mes = FACTORES_K_MES[mes_analisis]
    # Inicializar columnas adicionales
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
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            # Semilla más estable para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}")) % (2**32)
            rng = np.random.RandomState(seed_value)
            # Normalizar coordenadas para variabilidad espacial más realista
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            # SIMULACIÓN MÁS REALISTA DE PARÁMETROS DEL SUELO
            n_optimo = params['NITROGENO']['optimo']
            p_optimo = params['FOSFORO']['optimo']
            k_optimo = params['POTASIO']['optimo']
            # Variabilidad espacial más pronunciada
            variabilidad_local = 0.2 + 0.6 * (lat_norm * lon_norm)  # Mayor correlación espacial
            # Simular valores con distribución normal más realista
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
            # Aplicar factores estacionales mejorados
            nitrogeno *= factor_n_mes * (0.9 + 0.2 * rng.random())
            fosforo *= factor_p_mes * (0.9 + 0.2 * rng.random())
            potasio *= factor_k_mes * (0.9 + 0.2 * rng.random())
            # Parámetros adicionales del suelo simulados
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
            # NDVI con correlación con fertilidad
            base_ndvi = 0.3 + 0.5 * variabilidad_local
            ndvi = max(0.1, min(0.95, rng.normal(base_ndvi, 0.1)))
            # CÁLCULO MEJORADO DE ÍNDICE DE FERTILIDAD
            n_norm = max(0, min(1, nitrogeno / (n_optimo * 1.5)))  # Normalizado al 150% del óptimo
            p_norm = max(0, min(1, fosforo / (p_optimo * 1.5)))
            k_norm = max(0, min(1, potasio / (k_optimo * 1.5)))
            mo_norm = max(0, min(1, materia_organica / 8.0))
            ph_norm = max(0, min(1, 1 - abs(ph - params['pH_OPTIMO']) / 2.0))  # Óptimo en centro
            # Índice compuesto mejorado
            indice_fertilidad = (
                n_norm * 0.25 + 
                p_norm * 0.20 + 
                k_norm * 0.20 + 
                mo_norm * 0.15 +
                ph_norm * 0.10 +
                ndvi * 0.10
            ) * factor_mes
            indice_fertilidad = max(0, min(1, indice_fertilidad))
            # CATEGORIZACIÓN MEJORADA
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
            # 🔧 **CÁLCULO CORREGIDO DE RECOMENDACIONES NPK - MÁS PRECISO**
            if analisis_tipo == "RECOMENDACIONES NPK":
                if nutriente == "NITRÓGENO":
                    # Cálculo realista de recomendación de Nitrógeno
                    deficit_nitrogeno = max(0, n_optimo - nitrogeno)
                    # Factores de ajuste más precisos:
                    factor_eficiencia = 1.4  # 40% de pérdidas por lixiviación/volatilización
                    factor_crecimiento = 1.2  # 20% adicional para crecimiento óptimo
                    factor_materia_organica = max(0.7, 1.0 - (materia_organica / 15.0))  # MO aporta N
                    factor_ndvi = 1.0 + (0.5 - ndvi) * 0.4  # NDVI bajo = más necesidad
                    recomendacion = (deficit_nitrogeno * factor_eficiencia * factor_crecimiento * 
                                   factor_materia_organica * factor_ndvi)
                    # Límites realistas para nitrógeno
                    recomendacion = min(recomendacion, 250)  # Máximo 250 kg/ha
                    recomendacion = max(20, recomendacion)   # Mínimo 20 kg/ha
                    deficit = deficit_nitrogeno
                elif nutriente == "FÓSFORO":
                    # Cálculo realista de recomendación de Fósforo
                    deficit_fosforo = max(0, p_optimo - fosforo)
                    # Factores de ajuste para fósforo
                    factor_eficiencia = 1.6  # Alta fijación en el suelo
                    factor_ph = 1.0
                    if ph < 5.5 or ph > 7.5:  # Fuera del rango óptimo de disponibilidad
                        factor_ph = 1.3  # 30% más si el pH no es óptimo
                    factor_materia_organica = 1.1  # MO ayuda a la disponibilidad de P
                    recomendacion = (deficit_fosforo * factor_eficiencia * 
                                   factor_ph * factor_materia_organica)
                    # Límites realistas para fósforo
                    recomendacion = min(recomendacion, 120)  # Máximo 120 kg/ha P2O5
                    recomendacion = max(10, recomendacion)   # Mínimo 10 kg/ha
                    deficit = deficit_fosforo
                else:  # POTASIO
                    # Cálculo realista de recomendación de Potasio
                    deficit_potasio = max(0, k_optimo - potasio)
                    # Factores de ajuste para potasio
                    factor_eficiencia = 1.3  # Moderada lixiviación
                    factor_textura = 1.0
                    if materia_organica < 2.0:  # Suelos arenosos
                        factor_textura = 1.2  # 20% más en suelos ligeros
                    factor_rendimiento = 1.0 + (0.5 - ndvi) * 0.3  # NDVI bajo = más necesidad
                    recomendacion = (deficit_potasio * factor_eficiencia * 
                                   factor_textura * factor_rendimiento)
                    # Límites realistas para potasio
                    recomendacion = min(recomendacion, 200)  # Máximo 200 kg/ha K2O
                    recomendacion = max(15, recomendacion)   # Mínimo 15 kg/ha
                    deficit = deficit_potasio
                # Ajuste final basado en la categoría de fertilidad
                if categoria in ["MUY BAJA", "BAJA"]:
                    recomendacion *= 1.3  # 30% más en suelos de baja fertilidad
                elif categoria in ["ALTA", "MUY ALTA", "EXCELENTE"]:
                    recomendacion *= 0.8  # 20% menos en suelos fértiles
            else:
                recomendacion = 0
                deficit = 0
            # Asignar valores al GeoDataFrame
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
            # Valores por defecto mejorados en caso de error
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
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
