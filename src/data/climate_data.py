import requests
import pandas as pd
from datetime import datetime

def obtener_datos_nasa_power(lat, lon, mes_analisis):
    """
    Obtiene datos mensuales promedio de NASA POWER para un punto y mes.
    """
    # Mapear mes a número
    mes_num = {
        "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
        "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
    }[mes_analisis]
    
    # Año actual
    año = datetime.now().year
    
    # Fechas de inicio y fin del mes
    start = f"{año}{mes_num:02d}01"
    if mes_num == 12:
        end = f"{año+1}0101"
    else:
        end = f"{año}{mes_num+1:02d}01"
    
    # API de NASA POWER
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
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Extraer promedios mensuales
            dias = data['properties']['parameter']
            rad_solar = np.nanmean(list(dias['ALLSKY_SFC_SW_DWN'].values()))
            precip = np.nanmean(list(dias['PRECTOTCORR'].values()))
            viento = np.nanmean(list(dias['WS10M'].values()))
            
            return {
                'radiacion_solar': rad_solar,  # MJ/m²/día
                'precipitacion': precip,       # mm/día
                'velocidad_viento': viento     # m/s
            }
        else:
            return None
    except Exception as e:
        return None
