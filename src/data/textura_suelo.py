import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
from src.utils.constants import (
    TEXTURA_SUELO_OPTIMA,
    CLASIFICACION_TEXTURAS,
    FACTORES_SUELO,
    RECOMENDACIONES_TEXTURA
)
from src.data.file_loader import calcular_superficie

def clasificar_textura_suelo(arena, limo, arcilla):
    """Clasifica la textura del suelo según el triángulo de texturas USDA"""
    try:
        # Normalizar porcentajes a 100%
        total = arena + limo + arcilla
        if total == 0:
            return "NO_DETERMINADA"
        arena_norm = (arena / total) * 100
        limo_norm = (limo / total) * 100
        arcilla_norm = (arcilla / total) * 100
        # Clasificación según USDA - NOMBRES ACTUALIZADOS
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
            return "Franco"  # Por defecto
    except Exception as e:
        return "NO_DETERMINADA"

def calcular_propiedades_fisicas_suelo(textura, materia_organica):
    """Calcula propiedades físicas del suelo basadas en textura y MO"""
    propiedades = {
        'capacidad_campo': 0.0,
        'punto_marchitez': 0.0,
        'agua_disponible': 0.0,
        'densidad_aparente': 0.0,
        'porosidad': 0.0,
        'conductividad_hidraulica': 0.0
    }
    # Valores base según textura (mm/m) - NOMBRES ACTUALIZADOS
    base_propiedades = {
        'Arcilloso': {'cc': 350, 'pm': 200, 'da': 1.3, 'porosidad': 0.5, 'kh': 0.1},
        'Franco Arcilloso': {'cc': 300, 'pm': 150, 'da': 1.25, 'porosidad': 0.53, 'kh': 0.5},
        'Franco': {'cc': 250, 'pm': 100, 'da': 1.2, 'porosidad': 0.55, 'kh': 1.5},
        'Franco Arcilloso-Arenoso': {'cc': 180, 'pm': 80, 'da': 1.35, 'porosidad': 0.49, 'kh': 5.0},
        'Arenoso': {'cc': 120, 'pm': 50, 'da': 1.5, 'porosidad': 0.43, 'kh': 15.0}
    }
    if textura in base_propiedades:
        base = base_propiedades[textura]
        # Ajustar por materia orgánica (cada 1% de MO mejora propiedades)
        factor_mo = 1.0 + (materia_organica * 0.05)
        propiedades['capacidad_campo'] = base['cc'] * factor_mo
        propiedades['punto_marchitez'] = base['pm'] * factor_mo
        propiedades['agua_disponible'] = (base['cc'] - base['pm']) * factor_mo
        propiedades['densidad_aparente'] = base['da'] / factor_mo
        propiedades['porosidad'] = min(0.65, base['porosidad'] * factor_mo)
        propiedades['conductividad_hidraulica'] = base['kh'] * factor_mo
    return propiedades

def evaluar_adecuacion_textura(textura_actual, cultivo):
    """Evalúa qué tan adecuada es la textura para el cultivo específico"""
    textura_optima = TEXTURA_SUELO_OPTIMA[cultivo]['textura_optima']
    # Jerarquía de adecuación - NOMBRES ACTUALIZADOS
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
    """Realiza análisis completo de textura del suelo"""
    params_textura = TEXTURA_SUELO_OPTIMA[cultivo]
    zonas_gdf = gdf.copy()
    # Inicializar columnas para textura
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
            # Calcular área
            area_ha = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            # Obtener centroide
            if hasattr(row.geometry, 'centroid'):
                centroid = row.geometry.centroid
            else:
                centroid = row.geometry.representative_point()
            # Semilla para reproducibilidad
            seed_value = abs(hash(f"{centroid.x:.6f}_{centroid.y:.6f}_{cultivo}_textura")) % (2**32)
            rng = np.random.RandomState(seed_value)
            # Normalizar coordenadas para variabilidad espacial
            lat_norm = (centroid.y + 90) / 180 if centroid.y else 0.5
            lon_norm = (centroid.x + 180) / 360 if centroid.x else 0.5
            # SIMULAR COMPOSICIÓN GRANULOMÉTRICA MÁS REALISTA
            variabilidad_local = 0.15 + 0.7 * (lat_norm * lon_norm)
            # Valores óptimos para el cultivo
            arena_optima = params_textura['arena_optima']
            limo_optima = params_textura['limo_optima']
            arcilla_optima = params_textura['arcilla_optima']
            # Simular composición con distribución normal
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
            # Normalizar a 100%
            total = arena + limo + arcilla
            arena = (arena / total) * 100
            limo = (limo / total) * 100
            arcilla = (arcilla / total) * 100
            # Clasificar textura
            textura = clasificar_textura_suelo(arena, limo, arcilla)
            # Evaluar adecuación para el cultivo
            categoria_adecuacion, puntaje_adecuacion = evaluar_adecuacion_textura(textura, cultivo)
            # Simular materia orgánica para propiedades físicas
            materia_organica = max(1.0, min(8.0, rng.normal(3.0, 1.0)))
            # Calcular propiedades físicas
            propiedades_fisicas = calcular_propiedades_fisicas_suelo(textura, materia_organica)
            # Asignar valores al GeoDataFrame
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
        except Exception as e:
            # Valores por defecto en caso de error
            zonas_gdf.loc[idx, 'area_ha'] = calcular_superficie(zonas_gdf.iloc[[idx]]).iloc[0]
            zonas_gdf.loc[idx, 'arena'] = params_textura['arena_optima']
            zonas_gdf.loc[idx, 'limo'] = params_textura['limo_optima']
            zonas_gdf.loc[idx, 'arcilla'] = params_textura['arcilla_optima']
            zonas_gdf.loc[idx, 'textura_suelo'] = params_textura['textura_optima']
            zonas_gdf.loc[idx, 'adecuacion_textura'] = 1.0
            zonas_gdf.loc[idx, 'categoria_adecuacion'] = "ÓPTIMA"
            # Propiedades físicas por defecto
            propiedades_default = calcular_propiedades_fisicas_suelo(params_textura['textura_optima'], 3.0)
            for prop, valor in propiedades_default.items():
                zonas_gdf.loc[idx, prop] = valor
    return zonas_gdf
