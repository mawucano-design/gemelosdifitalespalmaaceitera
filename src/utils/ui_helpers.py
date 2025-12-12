import streamlit as st
import geopandas as gpd
import numpy as np
from streamlit_folium import st_folium
from datetime import datetime
from shapely.geometry import Polygon
from src.data.file_loader import calcular_superficie, procesar_archivo
from src.core.division_zonas import dividir_parcela_en_zonas
from src.core.indices_gee import calcular_indices_gee
from src.data.textura_suelo import analizar_textura_suelo
from src.visualization.maps import crear_mapa_interactivo, crear_mapa_visualizador_parcela
from src.agroecology.recommendations import mostrar_recomendaciones_agroecologicas
from src.utils.pdf_generator import generar_informe_pdf


def mostrar_resultados_textura():
    """Muestra los resultados del análisis de textura"""
    if st.session_state.analisis_textura is None:
        st.warning("No hay datos de análisis de textura disponibles")
        return
    gdf_textura = st.session_state.analisis_textura
    area_total = st.session_state.area_total
    cultivo = st.session_state.cultivo
    mes_analisis = st.session_state.mes_analisis
    
    st.markdown("## 🏗️ ANÁLISIS DE TEXTURA DEL SUELO")
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración", key="volver_textura"):
        st.session_state.analisis_completado = False
        st.rerun()
    # Estadísticas resumen
    st.subheader("📊 Estadísticas del Análisis de Textura")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "NO_DETERMINADA"
        st.metric("🏗️ Textura Predominante", textura_predominante)
    with col2:
        avg_adecuacion = gdf_textura['adecuacion_textura'].mean()
        st.metric("📊 Adecuación Promedio", f"{avg_adecuacion:.1%}")
    with col3:
        avg_arena = gdf_textura['arena'].mean()
        st.metric("🏖️ Arena Promedio", f"{avg_arena:.1f}%")
    with col4:
        avg_arcilla = gdf_textura['arcilla'].mean()
        st.metric("🧱 Arcilla Promedio", f"{avg_arcilla:.1f}%")
    # Estadísticas adicionales
    col5, col6, col7 = st.columns(3)
    with col5:
        avg_limo = gdf_textura['limo'].mean()
        st.metric("🌫️ Limo Promedio", f"{avg_limo:.1f}%")
    with col6:
        avg_agua_disp = gdf_textura['agua_disponible'].mean()
        st.metric("💧 Agua Disponible Promedio", f"{avg_agua_disp:.0f} mm/m")
    with col7:
        avg_densidad = gdf_textura['densidad_aparente'].mean()
        st.metric("⚖️ Densidad Aparente", f"{avg_densidad:.2f} g/cm³")
    # Distribución de texturas
    st.subheader("📋 Distribución de Texturas del Suelo")
    textura_dist = gdf_textura['textura_suelo'].value_counts()
    st.bar_chart(textura_dist)
    # Gráfico de composición granulométrica
    st.subheader("🔺 Composición Granulométrica Promedio")
    fig, ax = st.pyplot().__class__.gca().figure, st.pyplot().__class__.gca()
    # Datos para el gráfico de torta
    composicion = [
        gdf_textura['arena'].mean(),
        gdf_textura['limo'].mean(), 
        gdf_textura['arcilla'].mean()
    ]
    labels = ['Arena', 'Limo', 'Arcilla']
    colors = ['#d8b365', '#f6e8c3', '#01665e']
    ax.pie(composicion, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax.set_title('Composición Promedio del Suelo')
    st.pyplot(fig)
    # Mapa de texturas
    st.subheader("🗺️ Mapa de Texturas del Suelo")
    mapa_textura = crear_mapa_interactivo(
        gdf_textura, 
        f"Textura del Suelo - {cultivo.replace('_', ' ').title()}", 
        'textura_suelo', 
        "ANÁLISIS DE TEXTURA"
    )
    st_folium(mapa_textura, width=800, height=500)
    # Tabla detallada
    st.subheader("📋 Tabla de Resultados por Zona")
    columnas_textura = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla', 'capacidad_campo', 'agua_disponible']
    df_textura = gdf_textura[columnas_textura].copy()
    df_textura['area_ha'] = df_textura['area_ha'].round(3)
    df_textura['arena'] = df_textura['arena'].round(1)
    df_textura['limo'] = df_textura['limo'].round(1)
    df_textura['arcilla'] = df_textura['arcilla'].round(1)
    df_textura['capacidad_campo'] = df_textura['capacidad_campo'].round(1)
    df_textura['agua_disponible'] = df_textura['agua_disponible'].round(1)
    st.dataframe(df_textura, use_container_width=True)
    # Recomendaciones específicas para textura
    textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "Franco"
    adecuacion_promedio = gdf_textura['adecuacion_textura'].mean()
    textura_data = {
        'textura_predominante': textura_predominante,
        'adecuacion_promedio': adecuacion_promedio
    }
    mostrar_recomendaciones_agroecologicas(
        cultivo, "", area_total, "ANÁLISIS DE TEXTURA", None, textura_data
    )
    # DESCARGAR RESULTADOS
    st.markdown("### 💾 Descargar Resultados")
    col1, col2, col3 = st.columns(3)
    with col1:
        columnas_descarga = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']
        df_descarga = gdf_textura[columnas_descarga].copy()
        df_descarga['area_ha'] = df_descarga['area_ha'].round(3)
        df_descarga['adecuacion_textura'] = df_descarga['adecuacion_textura'].round(3)
        df_descarga['arena'] = df_descarga['arena'].round(1)
        df_descarga['limo'] = df_descarga['limo'].round(1)
        df_descarga['arcilla'] = df_descarga['arcilla'].round(1)
        csv = df_descarga.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Tabla CSV",
            data=csv,
            file_name=f"textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    with col2:
        geojson = gdf_textura.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    with col3:
        if st.button("📄 Generar Informe PDF", type="primary", key="pdf_textura"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_textura, cultivo, "ANÁLISIS DE TEXTURA", "", mes_analisis, area_total, gdf_textura
                )
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_textura_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )


def mostrar_resultados_principales():
    """Muestra los resultados del análisis principal"""
    gdf_analisis = st.session_state.gdf_analisis
    area_total = st.session_state.area_total
    cultivo = st.session_state.cultivo
    analisis_tipo = st.session_state.analisis_tipo
    nutriente = st.session_state.nutriente
    mes_analisis = st.session_state.mes_analisis
    
    st.markdown("## 📈 RESULTADOS DEL ANÁLISIS PRINCIPAL")
    # Botón para volver atrás
    if st.button("⬅️ Volver a Configuración", key="volver_principal"):
        st.session_state.analisis_completado = False
        st.rerun()
    # Estadísticas resumen
    st.subheader("📊 Estadísticas del Análisis")
    if analisis_tipo == "FERTILIDAD ACTUAL":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            avg_fert = gdf_analisis['indice_fertilidad'].mean()
            st.metric("📊 Índice Fertilidad Promedio", f"{avg_fert:.3f}")
        with col2:
            avg_n = gdf_analisis['nitrogeno'].mean()
            st.metric("🌿 Nitrógeno Promedio", f"{avg_n:.1f} kg/ha")
        with col3:
            avg_p = gdf_analisis['fosforo'].mean()
            st.metric("🧪 Fósforo Promedio", f"{avg_p:.1f} kg/ha")
        with col4:
            avg_k = gdf_analisis['potasio'].mean()
            st.metric("⚡ Potasio Promedio", f"{avg_k:.1f} kg/ha")
        col5, col6, col7 = st.columns(3)
        with col5:
            avg_mo = gdf_analisis['materia_organica'].mean()
            st.metric("🌱 Materia Orgánica Promedio", f"{avg_mo:.1f}%")
        with col6:
            avg_ndvi = gdf_analisis['ndvi'].mean()
            st.metric("📡 NDVI Promedio", f"{avg_ndvi:.3f}")
        with col7:
            zona_prioridad = gdf_analisis['prioridad'].value_counts().index[0]
            st.metric("🎯 Prioridad Predominante", zona_prioridad)
        st.subheader("📋 Distribución de Categorías de Fertilidad")
        cat_dist = gdf_analisis['categoria'].value_counts()
        st.bar_chart(cat_dist)
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_rec = gdf_analisis['recomendacion_npk'].mean()
            st.metric(f"💡 Recomendación {nutriente} Promedio", f"{avg_rec:.1f} kg/ha")
        with col2:
            total_rec = (gdf_analisis['recomendacion_npk'] * gdf_analisis['area_ha']).sum()
            st.metric(f"📦 Total {nutriente} Requerido", f"{total_rec:.1f} kg")
        with col3:
            zona_prioridad = gdf_analisis['prioridad'].value_counts().index[0]
            st.metric("🎯 Prioridad Aplicación", zona_prioridad)
        st.subheader("🌿 Estado Actual de Nutrientes")
        col_n, col_p, col_k, col_mo = st.columns(4)
        with col_n:
            avg_n = gdf_analisis['nitrogeno'].mean()
            st.metric("Nitrógeno", f"{avg_n:.1f} kg/ha")
        with col_p:
            avg_p = gdf_analisis['fosforo'].mean()
            st.metric("Fósforo", f"{avg_p:.1f} kg/ha")
        with col_k:
            avg_k = gdf_analisis['potasio'].mean()
            st.metric("Potasio", f"{avg_k:.1f} kg/ha")
        with col_mo:
            avg_mo = gdf_analisis['materia_organica'].mean()
            st.metric("Materia Orgánica", f"{avg_mo:.1f}%")
    # MAPAS INTERACTIVOS
    st.markdown("### 🗺️ Mapas de Análisis")
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columna_visualizar = 'indice_fertilidad'
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
    else:
        columna_visualizar = 'recomendacion_npk'
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
    mapa_analisis = crear_mapa_interactivo(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    st_folium = st_folium or __import__('streamlit_folium', fromlist=['st_folium']).st_folium
    st_folium(mapa_analisis, width=800, height=500)
    # MAPA ESTÁTICO PARA DESCARGA
    st.markdown("### 📄 Mapa para Reporte")
    from src.visualization.maps import crear_mapa_estatico
    mapa_estatico = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    if mapa_estatico:
        st.image(mapa_estatico, caption=titulo_mapa, use_column_width=True)
    # TABLA DETALLADA
    st.markdown("### 📋 Tabla de Resultados por Zona")
    columnas_tabla = ['id_zona', 'area_ha', 'categoria', 'prioridad']
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'materia_organica', 'ndvi'])
    else:
        columnas_tabla.extend(['recomendacion_npk', 'deficit_npk', 'nitrogeno', 'fosforo', 'potasio'])
    df_tabla = gdf_analisis[columnas_tabla].copy()
    df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
        df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
        df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
        df_tabla['potasio'] = df_tabla['potasio'].round(1)
        df_tabla['materia_organica'] = df_tabla['materia_organica'].round(1)
        df_tabla['ndvi'] = df_tabla['ndvi'].round(3)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
        df_tabla['deficit_npk'] = df_tabla['deficit_npk'].round(1)
    st.dataframe(df_tabla, use_container_width=True)
    # RECOMENDACIONES AGROECOLÓGICAS
    categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
    mostrar_recomendaciones_agroecologicas(
        cultivo, categoria_promedio, area_total, analisis_tipo, nutriente
    )
    # DESCARGAR RESULTADOS
    st.markdown("### 💾 Descargar Resultados")
    col1, col2, col3 = st.columns(3)
    with col1:
        csv = df_tabla.to_csv(index=False)
        st.download_button(
            label="📥 Descargar Tabla CSV",
            data=csv,
            file_name=f"resultados_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )
    with col2:
        geojson = gdf_analisis.to_json()
        st.download_button(
            label="🗺️ Descargar GeoJSON",
            data=geojson,
            file_name=f"zonas_analisis_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
            mime="application/json"
        )
    with col3:
        if st.button("📄 Generar Informe PDF", type="primary", key="pdf_principal"):
            with st.spinner("🔄 Generando informe PDF..."):
                pdf_buffer = generar_informe_pdf(
                    gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total, st.session_state.analisis_textura
                )
                st.download_button(
                    label="📥 Descargar Informe PDF",
                    data=pdf_buffer,
                    file_name=f"informe_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf"
                )


def mostrar_modo_demo():
    """Muestra la interfaz de demostración"""
    st.markdown("### 🚀 Modo Demostración")
    st.info("""
    **Para usar la aplicación:**
    1. Sube un archivo ZIP con el shapefile de tu parcela
    2. Selecciona el cultivo y tipo de análisis
    3. Configura los parámetros en el sidebar
    4. Ejecuta el análisis GEE
    **📁 El shapefile debe incluir:**
    - .shp (geometrías)
    - .shx (índice)
    - .dbf (atributos)
    - .prj (sistema de coordenadas)
    **NUEVO: Análisis de Textura del Suelo**
    - Clasificación USDA de texturas
    - Propiedades físicas del suelo
    - Recomendaciones específicas por textura
    **🗺️ Mapas:** Usamos OpenStreetMap como base principal
    """)
    if st.button("🎯 Cargar Datos de Demostración", type="primary"):
        st.session_state.datos_demo = True
        # Crear polígono de ejemplo
        poligono_ejemplo = Polygon([
            [-74.1, 4.6], [-74.0, 4.6], [-74.0, 4.7], [-74.1, 4.7], [-74.1, 4.6]
        ])
        gdf_demo = gpd.GeoDataFrame(
            {'id': [1], 'nombre': ['Parcela Demo']},
            geometry=[poligono_ejemplo],
            crs="EPSG:4326"
        )
        st.session_state.gdf_original = gdf_demo
        st.rerun()


def mostrar_configuracion_parcela():
    """Muestra la configuración de la parcela antes del análisis"""
    gdf_original = st.session_state.gdf_original
    cultivo = st.session_state.cultivo
    n_divisiones = st.session_state.n_divisiones
    area_total = calcular_superficie(gdf_original).sum()
    num_poligonos = len(gdf_original)
    
    st.success("✅ Parcela cargada correctamente")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📐 Área Total", f"{area_total:.2f} ha")
    with col2:
        st.metric("🔢 Número de Polígonos", num_poligonos)
    with col3:
        st.metric("🌱 Cultivo", cultivo.replace('_', ' ').title())
    # VISUALIZADOR DE PARCELA ORIGINAL
    st.markdown("### 🗺️ Visualizador de Parcela")
    st.info("🗺️ **Mapa base:** OpenStreetMap. Usa el control de capas para cambiar a ESRI Satélite o otras opciones.")
    mapa_parcela = crear_mapa_visualizador_parcela(gdf_original)
    st_folium = __import__('streamlit_folium', fromlist=['st_folium']).st_folium
    st_folium(mapa_parcela, width=800, height=500)
    # DIVIDIR PARCELA EN ZONAS
    st.markdown("### 📊 División en Zonas de Manejo")
    st.info(f"La parcela se dividirá en **{n_divisiones} zonas** para análisis detallado")
    if st.button("🚀 Ejecutar Análisis GEE Completo", type="primary"):
        with st.spinner("🔄 Dividiendo parcela en zonas..."):
            gdf_zonas = dividir_parcela_en_zonas(gdf_original, n_divisiones)
            st.session_state.gdf_zonas = gdf_zonas
        with st.spinner("🔬 Realizando análisis GEE..."):
            analisis_tipo = st.session_state.analisis_tipo
            nutriente = st.session_state.nutriente
            mes_analisis = st.session_state.mes_analisis
            if analisis_tipo == "ANÁLISIS DE TEXTURA":
                gdf_analisis = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                st.session_state.analisis_textura = gdf_analisis
            else:
                gdf_analisis = calcular_indices_gee(
                    gdf_zonas, cultivo, mes_analisis, analisis_tipo, nutriente
                )
                st.session_state.gdf_analisis = gdf_analisis
            if analisis_tipo != "ANÁLISIS DE TEXTURA":
                with st.spinner("🏗️ Realizando análisis de textura..."):
                    gdf_textura = analizar_textura_suelo(gdf_zonas, cultivo, mes_analisis)
                    st.session_state.analisis_textura = gdf_textura
            st.session_state.area_total = area_total
            st.session_state.analisis_completado = True
        st.rerun()
