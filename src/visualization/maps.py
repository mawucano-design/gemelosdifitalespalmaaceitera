import geopandas as gpd
import matplotlib.pyplot as plt
import io
from matplotlib.colors import LinearSegmentedColormap
from shapely.geometry import Polygon
import folium
from folium import plugins
from streamlit_folium import st_folium
from src.utils.constants import PALETAS_GEE
from src.data.file_loader import calcular_superficie

def crear_mapa_interactivo(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    """Crea mapa interactivo con base OpenStreetMap - MEJORADO"""
    # Obtener centro y bounds del GeoDataFrame
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    # Crear mapa centrado con OpenStreetMap por defecto
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=15,
        tiles='OpenStreetMap',
        attr='© OpenStreetMap contributors',
        name='OpenStreetMap'
    )
    # Añadir otras bases como opciones
    # ESRI Satélite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite',
        overlay=False
    ).add_to(m)
    # ESRI Calles
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Calles',
        overlay=False
    ).add_to(m)
    # CartoDB Positron (alternativa clara)
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='CartoDB',
        name='CartoDB Positron',
        overlay=False
    ).add_to(m)
    # OpenTopoMap (mapa topográfico)
    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr='OpenTopoMap',
        name='OpenTopoMap',
        overlay=False
    ).add_to(m)
    # CONFIGURAR RANGOS MEJORADOS
    if columna_valor and analisis_tipo:
        if analisis_tipo == "FERTILIDAD ACTUAL":
            vmin, vmax = 0, 1
            colores = PALETAS_GEE['FERTILIDAD']
            unidad = "Índice"
        elif analisis_tipo == "ANÁLISIS DE TEXTURA":
            # Mapa categórico para texturas - NOMBRES ACTUALIZADOS
            colores_textura = {
                'Arenoso': '#d8b365',
                'Franco Arcilloso-Arenoso': '#f6e8c3', 
                'Franco': '#c7eae5',
                'Franco Arcilloso': '#5ab4ac',
                'Arcilloso': '#01665e',
                'NO_DETERMINADA': '#999999'
            }
            unidad = "Textura"
        else:
            # RANGOS MÁS REALISTAS PARA RECOMENDACIONES
            if nutriente == "NITRÓGENO":
                vmin, vmax = 0, 250
                colores = PALETAS_GEE['NITROGENO']
                unidad = "kg/ha N"
            elif nutriente == "FÓSFORO":
                vmin, vmax = 0, 120
                colores = PALETAS_GEE['FOSFORO']
                unidad = "kg/ha P₂O₅"
            else:  # POTASIO
                vmin, vmax = 0, 200
                colores = PALETAS_GEE['POTASIO']
                unidad = "kg/ha K₂O"
        # Función para obtener color
        def obtener_color(valor, vmin, vmax, colores):
            if vmax == vmin:
                return colores[len(colores)//2]
            valor_norm = (valor - vmin) / (vmax - vmin)
            valor_norm = max(0, min(1, valor_norm))
            idx = int(valor_norm * (len(colores) - 1))
            return colores[idx]
        # Añadir cada polígono con estilo mejorado
        for idx, row in gdf.iterrows():
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                # Manejo especial para textura (valores categóricos)
                textura = row[columna_valor]
                color = colores_textura.get(textura, '#999999')
                valor_display = textura
            else:
                # Manejo para valores numéricos
                valor = row[columna_valor]
                color = obtener_color(valor, vmin, vmax, colores)
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    valor_display = f"{valor:.3f}"
                else:
                    valor_display = f"{valor:.1f}"
            # Popup más informativo
            if analisis_tipo == "FERTILIDAD ACTUAL":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Índice Fertilidad:</b> {valor_display}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <b>Categoría:</b> {row.get('categoria', 'N/A')}<br>
                    <b>Prioridad:</b> {row.get('prioridad', 'N/A')}<br>
                    <hr>
                    <b>N:</b> {row.get('nitrogeno', 0):.1f} kg/ha<br>
                    <b>P:</b> {row.get('fosforo', 0):.1f} kg/ha<br>
                    <b>K:</b> {row.get('potasio', 0):.1f} kg/ha<br>
                    <b>MO:</b> {row.get('materia_organica', 0):.1f}%<br>
                    <b>NDVI:</b> {row.get('ndvi', 0):.3f}
                </div>
                """
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Textura:</b> {valor_display}<br>
                    <b>Adecuación:</b> {row.get('adecuacion_textura', 0):.1%}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <hr>
                    <b>Arena:</b> {row.get('arena', 0):.1f}%<br>
                    <b>Limo:</b> {row.get('limo', 0):.1f}%<br>
                    <b>Arcilla:</b> {row.get('arcilla', 0):.1f}%<br>
                    <b>Capacidad Campo:</b> {row.get('capacidad_campo', 0):.1f} mm/m<br>
                    <b>Agua Disponible:</b> {row.get('agua_disponible', 0):.1f} mm/m
                </div>
                """
            else:
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px;">
                    <h4>Zona {row['id_zona']}</h4>
                    <b>Recomendación {nutriente}:</b> {valor_display} {unidad}<br>
                    <b>Área:</b> {row.get('area_ha', 0):.2f} ha<br>
                    <b>Categoría Fertilidad:</b> {row.get('categoria', 'N/A')}<br>
                    <b>Prioridad:</b> {row.get('prioridad', 'N/A')}<br>
                    <hr>
                    <b>N Actual:</b> {row.get('nitrogeno', 0):.1f} kg/ha<br>
                    <b>P Actual:</b> {row.get('fosforo', 0):.1f} kg/ha<br>
                    <b>K Actual:</b> {row.get('potasio', 0):.1f} kg/ha<br>
                    <b>Déficit:</b> {row.get('deficit_npk', 0):.1f} kg/ha
                </div>
                """
            # Estilo mejorado para los polígonos
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.7,
                    'opacity': 0.9
                },
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"Zona {row['id_zona']}: {valor_display}"
            ).add_to(m)
            # Marcador con número de zona mejorado
            centroid = row.geometry.centroid
            folium.Marker(
                [centroid.y, centroid.x],
                icon=folium.DivIcon(
                    html=f'''
                    <div style="
                        background-color: white; 
                        border: 2px solid black; 
                        border-radius: 50%; 
                        width: 28px; 
                        height: 28px; 
                        display: flex; 
                        align-items: center; 
                        justify-content: center; 
                        font-weight: bold; 
                        font-size: 11px;
                        color: black;
                    ">{row["id_zona"]}</div>
                    '''
                ),
                tooltip=f"Zona {row['id_zona']} - Click para detalles"
            ).add_to(m)
    else:
        # Mapa simple del polígono original
        for idx, row in gdf.iterrows():
            area_ha = calcular_superficie(gdf.iloc[[idx]]).iloc[0]
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
    # Ajustar bounds del mapa
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    # Añadir controles mejorados
    folium.LayerControl().add_to(m)
    plugins.MeasureControl(position='bottomleft', primary_length_unit='meters').add_to(m)
    plugins.MiniMap(toggle_display=True, position='bottomright').add_to(m)
    plugins.Fullscreen(position='topright').add_to(m)
    # Añadir leyenda mejorada
    if columna_valor and analisis_tipo:
        legend_html = f'''
        <div style="
            position: fixed; 
            top: 10px; 
            right: 10px; 
            width: 250px; 
            height: auto; 
            background-color: white; 
            border: 2px solid grey; 
            z-index: 9999; 
            font-size: 12px; 
            padding: 10px; 
            border-radius: 5px;
            font-family: Arial;
        ">
            <h4 style="margin:0 0 10px 0; text-align:center; color: #333;">{titulo}</h4>
            <div style="margin-bottom: 10px;">
                <strong>Escala de Valores ({unidad}):</strong>
            </div>
        '''
        if analisis_tipo == "FERTILIDAD ACTUAL":
            steps = 8
            for i in range(steps):
                value = i / (steps - 1)
                color_idx = int((i / (steps - 1)) * (len(PALETAS_GEE['FERTILIDAD']) - 1))
                color = PALETAS_GEE['FERTILIDAD'][color_idx]
                categoria = ["Muy Baja", "Baja", "Media-Baja", "Media", "Media-Alta", "Alta", "Muy Alta"][min(i, 6)] if i < 7 else "Óptima"
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {value:.1f} ({categoria})</div>'
        elif analisis_tipo == "ANÁLISIS DE TEXTURA":
            # Leyenda categórica para texturas - NOMBRES ACTUALIZADOS
            colores_textura = {
                'Arenoso': '#d8b365',
                'Franco Arcilloso-Arenoso': '#f6e8c3', 
                'Franco': '#c7eae5',
                'Franco Arcilloso': '#5ab4ac',
                'Arcilloso': '#01665e'
            }
            for textura, color in colores_textura.items():
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {textura}</div>'
        else:
            steps = 6
            for i in range(steps):
                value = vmin + (i / (steps - 1)) * (vmax - vmin)
                color_idx = int((i / (steps - 1)) * (len(colores) - 1))
                color = colores[color_idx]
                intensidad = ["Muy Baja", "Baja", "Media", "Alta", "Muy Alta", "Máxima"][i]
                legend_html += f'<div style="margin:2px 0;"><span style="background:{color}; width:20px; height:15px; display:inline-block; margin-right:5px; border:1px solid #000;"></span> {value:.0f} ({intensidad})</div>'
        legend_html += '''
            <div style="margin-top: 10px; font-size: 10px; color: #666;">
                💡 Click en las zonas para detalles<br>
                🗺️ Usa el control de capas para cambiar el mapa base
            </div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    return m

def crear_mapa_visualizador_parcela(gdf):
    """Crea mapa interactivo para visualizar la parcela original con OpenStreetMap"""
    # Obtener centro y bounds
    centroid = gdf.geometry.centroid.iloc[0]
    bounds = gdf.total_bounds
    # Crear mapa con OpenStreetMap por defecto
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=14,
        tiles='OpenStreetMap',
        attr='© OpenStreetMap contributors',
        name='OpenStreetMap'
    )
    # Añadir otras bases
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite',
        overlay=False
    ).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Calles',
        overlay=False
    ).add_to(m)
    # Añadir polígonos de la parcela
    for idx, row in gdf.iterrows():
        area_ha = calcular_superficie(gdf.iloc[[idx]]).iloc[0]
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
    # Ajustar bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    # Añadir controles
    folium.LayerControl().add_to(m)
    plugins.MeasureControl(position='bottomleft').add_to(m)
    plugins.MiniMap(toggle_display=True).add_to(m)
    plugins.Fullscreen(position='topright').add_to(m)
    # Añadir leyenda
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 200px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>🌱 Visualizador de Parcela</b></p>
    <p><b>Leyenda:</b></p>
    <p><i style="background:#1f77b4; width:20px; height:20px; display:inline-block; margin-right:5px; opacity:0.4;"></i> Área de la parcela</p>
    <p><i style="background:#2ca02c; width:20px; height:20px; display:inline-block; margin_right:5px; opacity:0.8;"></i> Borde de la parcela</p>
    <p><small>🗺️ Usa el control de capas para cambiar el mapa base</small></p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    return m

def crear_mapa_estatico(gdf, titulo, columna_valor=None, analisis_tipo=None, nutriente=None):
    """Crea mapa estático con matplotlib - CORREGIDO PARA COINCIDIR CON INTERACTIVO"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        # CONFIGURACIÓN UNIFICADA CON EL MAPA INTERACTIVO
        if columna_valor and analisis_tipo:
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
                vmin, vmax = 0, 1
            elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                # Mapa categórico para texturas - NOMBRES ACTUALIZADOS
                colores_textura = {
                    'Arenoso': '#d8b365',
                    'Franco Arcilloso-Arenoso': '#f6e8c3', 
                    'Franco': '#c7eae5',
                    'Franco Arcilloso': '#5ab4ac',
                    'Arcilloso': '#01665e',
                    'NO_DETERMINADA': '#999999'
                }
            else:
                # USAR EXACTAMENTE LOS MISMOS RANGOS QUE EL MAPA INTERACTIVO
                if nutriente == "NITRÓGENO":
                    cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
                    vmin, vmax = 0, 250
                elif nutriente == "FÓSFORO":
                    cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
                    vmin, vmax = 0, 120
                else:  # POTASIO
                    cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
                    vmin, vmax = 0, 200
            # Plotear cada polígono con color según valor - MÉTODO UNIFICADO
            for idx, row in gdf.iterrows():
                if analisis_tipo == "ANÁLISIS DE TEXTURA":
                    # Manejo especial para textura
                    textura = row[columna_valor]
                    color = colores_textura.get(textura, '#999999')
                else:
                    valor = row[columna_valor]
                    valor_norm = (valor - vmin) / (vmax - vmin)
                    valor_norm = max(0, min(1, valor_norm))
                    color = cmap(valor_norm)
                # Plot del polígono
                gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1)
                # Etiqueta con valor - FORMATO MEJORADO
                centroid = row.geometry.centroid
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    texto_valor = f"{row[columna_valor]:.3f}"
                elif analisis_tipo == "ANÁLISIS DE TEXTURA":
                    texto_valor = row[columna_valor]
                else:
                    texto_valor = f"{row[columna_valor]:.0f} kg"
                ax.annotate(f"Z{row['id_zona']}\n{texto_valor}", 
                           (centroid.x, centroid.y), 
                           xytext=(3, 3), textcoords="offset points", 
                           fontsize=6, color='black', weight='bold',
                           bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8),
                           ha='center', va='center')
        else:
            # Mapa simple del polígono original
            gdf.plot(ax=ax, color='lightblue', edgecolor='black', linewidth=2, alpha=0.7)
        # Configuración del mapa
        ax.set_title(f'🗺️ {titulo}', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        # BARRA DE COLORES UNIFICADA
        if columna_valor and analisis_tipo and analisis_tipo != "ANÁLISIS DE TEXTURA":
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
            # Etiquetas de barra unificadas
            if analisis_tipo == "FERTILIDAD ACTUAL":
                cbar.set_label('Índice NPK Actual (0-1)', fontsize=10)
                # Marcas específicas para fertilidad
                cbar.set_ticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
                cbar.set_ticklabels(['0.0 (Muy Baja)', '0.2', '0.4 (Media)', '0.6', '0.8', '1.0 (Muy Alta)'])
            else:
                cbar.set_label(f'Recomendación {nutriente} (kg/ha)', fontsize=10)
                # Marcas específicas para recomendaciones
                if nutriente == "NITRÓGENO":
                    cbar.set_ticks([0, 50, 100, 150, 200, 250])
                    cbar.set_ticklabels(['0', '50', '100', '150', '200', '250 kg/ha'])
                elif nutriente == "FÓSFORO":
                    cbar.set_ticks([0, 24, 48, 72, 96, 120])
                    cbar.set_ticklabels(['0', '24', '48', '72', '96', '120 kg/ha'])
                else:  # POTASIO
                    cbar.set_ticks([0, 40, 80, 120, 160, 200])
                    cbar.set_ticklabels(['0', '40', '80', '120', '160', '200 kg/ha'])
        plt.tight_layout()
        # Convertir a imagen
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        import streamlit as st
        st.error(f"Error creando mapa estático: {str(e)}")
        return None
