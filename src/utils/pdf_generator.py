import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from src.visualization.maps import crear_mapa_estatico
from src.utils.constants import RECOMENDACIONES_AGROECOLOGICAS, RECOMENDACIONES_TEXTURA


def generar_informe_pdf(gdf_analisis, cultivo, analisis_tipo, nutriente, mes_analisis, area_total, gdf_textura=None):
    """Genera un informe PDF completo con los resultados del análisis"""
    # Crear buffer para el PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
    styles = getSampleStyleSheet()
    # Crear estilos personalizados
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.darkgreen,
        spaceAfter=30,
        alignment=1  # Centrado
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.darkblue,
        spaceAfter=12,
        spaceBefore=12
    )
    normal_style = styles['Normal']
    # Contenido del PDF
    story = []
    # Título principal
    story.append(Paragraph("INFORME DE ANÁLISIS AGRÍCOLA", title_style))
    story.append(Spacer(1, 20))
    # Información general
    story.append(Paragraph("INFORMACIÓN GENERAL", heading_style))
    info_data = [
        ["Cultivo:", cultivo.replace('_', ' ').title()],
        ["Tipo de Análisis:", analisis_tipo],
        ["Mes de Análisis:", mes_analisis],
        ["Área Total:", f"{area_total:.2f} ha"],
        ["Fecha de Generación:", datetime.now().strftime("%d/%m/%Y %H:%M")]
    ]
    if analisis_tipo == "RECOMENDACIONES NPK":
        info_data.insert(2, ["Nutriente Analizado:", nutriente])
    info_table = Table(info_data, colWidths=[2*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    # Estadísticas resumen
    story.append(Paragraph("ESTADÍSTICAS DEL ANÁLISIS", heading_style))
    if analisis_tipo == "FERTILIDAD ACTUAL":
        stats_data = [
            ["Estadística", "Valor"],
            ["Índice Fertilidad Promedio", f"{gdf_analisis['indice_fertilidad'].mean():.3f}"],
            ["Nitrógeno Promedio (kg/ha)", f"{gdf_analisis['nitrogeno'].mean():.1f}"],
            ["Fósforo Promedio (kg/ha)", f"{gdf_analisis['fosforo'].mean():.1f}"],
            ["Potasio Promedio (kg/ha)", f"{gdf_analisis['potasio'].mean():.1f}"],
            ["Materia Orgánica Promedio (%)", f"{gdf_analisis['materia_organica'].mean():.1f}"],
            ["NDVI Promedio", f"{gdf_analisis['ndvi'].mean():.3f}"]
        ]
    elif analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        stats_data = [
            ["Estadística", "Valor"],
            ["Textura Predominante", gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "N/A"],
            ["Adecuación Promedio", f"{gdf_textura['adecuacion_textura'].mean():.1%}"],
            ["Arena Promedio (%)", f"{gdf_textura['arena'].mean():.1f}"],
            ["Limo Promedio (%)", f"{gdf_textura['limo'].mean():.1f}"],
            ["Arcilla Promedio (%)", f"{gdf_textura['arcilla'].mean():.1f}"],
            ["Agua Disponible Promedio (mm/m)", f"{gdf_textura['agua_disponible'].mean():.0f}"]
        ]
    else:
        avg_rec = gdf_analisis['recomendacion_npk'].mean()
        total_rec = (gdf_analisis['recomendacion_npk'] * gdf_analisis['area_ha']).sum()
        stats_data = [
            ["Estadística", "Valor"],
            [f"Recomendación {nutriente} Promedio (kg/ha)", f"{avg_rec:.1f}"],
            [f"Total {nutriente} Requerido (kg)", f"{total_rec:.1f}"],
            ["Nitrógeno Promedio (kg/ha)", f"{gdf_analisis['nitrogeno'].mean():.1f}"],
            ["Fósforo Promedio (kg/ha)", f"{gdf_analisis['fosforo'].mean():.1f}"],
            ["Potasio Promedio (kg/ha)", f"{gdf_analisis['potasio'].mean():.1f}"]
        ]
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 20))
    # Distribución de categorías
    if analisis_tipo == "FERTILIDAD ACTUAL":
        story.append(Paragraph("DISTRIBUCIÓN DE CATEGORÍAS DE FERTILIDAD", heading_style))
        cat_dist = gdf_analisis['categoria'].value_counts()
        cat_data = [["Categoría", "Número de Zonas", "Porcentaje"]]
        total_zonas = len(gdf_analisis)
        for categoria, count in cat_dist.items():
            porcentaje = (count / total_zonas) * 100
            cat_data.append([categoria, str(count), f"{porcentaje:.1f}%"])
        cat_table = Table(cat_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 20))
    # Mapa estático
    story.append(PageBreak())
    story.append(Paragraph("MAPA DE ANÁLISIS", heading_style))
    # Generar mapa estático para el PDF
    if analisis_tipo == "FERTILIDAD ACTUAL":
        titulo_mapa = f"Fertilidad Actual - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'indice_fertilidad'
    elif analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        titulo_mapa = f"Textura del Suelo - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'textura_suelo'
        gdf_analisis = gdf_textura
    else:
        titulo_mapa = f"Recomendación {nutriente} - {cultivo.replace('_', ' ').title()}"
        columna_visualizar = 'recomendacion_npk'
    mapa_buffer = crear_mapa_estatico(
        gdf_analisis, titulo_mapa, columna_visualizar, analisis_tipo, nutriente
    )
    if mapa_buffer:
        try:
            # Convertir a imagen para PDF
            mapa_buffer.seek(0)
            img = Image(mapa_buffer, width=6*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"Figura 1: {titulo_mapa}", normal_style))
        except Exception as e:
            story.append(Paragraph("Error al generar el mapa para el PDF", normal_style))
    story.append(Spacer(1, 20))
    # Tabla de resultados por zona (primeras 10 zonas)
    story.append(Paragraph("RESULTADOS POR ZONA (PRIMERAS 10 ZONAS)", heading_style))
    # Preparar datos para tabla
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        columnas_tabla = ['id_zona', 'area_ha', 'textura_suelo', 'adecuacion_textura', 'arena', 'limo', 'arcilla']
        df_tabla = gdf_textura[columnas_tabla].head(10).copy()
    else:
        columnas_tabla = ['id_zona', 'area_ha', 'categoria', 'prioridad']
        if analisis_tipo == "FERTILIDAD ACTUAL":
            columnas_tabla.extend(['indice_fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'materia_organica'])
        else:
            columnas_tabla.extend(['recomendacion_npk', 'deficit_npk', 'nitrogeno', 'fosforo', 'potasio'])
        df_tabla = gdf_analisis[columnas_tabla].head(10).copy()
    # Redondear valores
    df_tabla['area_ha'] = df_tabla['area_ha'].round(3)
    if analisis_tipo == "FERTILIDAD ACTUAL":
        df_tabla['indice_fertilidad'] = df_tabla['indice_fertilidad'].round(3)
    elif analisis_tipo == "ANÁLISIS DE TEXTURA":
        df_tabla['adecuacion_textura'] = df_tabla['adecuacion_textura'].round(3)
        df_tabla['arena'] = df_tabla['arena'].round(1)
        df_tabla['limo'] = df_tabla['limo'].round(1)
        df_tabla['arcilla'] = df_tabla['arcilla'].round(1)
    else:
        df_tabla['recomendacion_npk'] = df_tabla['recomendacion_npk'].round(1)
        df_tabla['deficit_npk'] = df_tabla['deficit_npk'].round(1)
    if 'nitrogeno' in df_tabla.columns:
        df_tabla['nitrogeno'] = df_tabla['nitrogeno'].round(1)
    if 'fosforo' in df_tabla.columns:
        df_tabla['fosforo'] = df_tabla['fosforo'].round(1)
    if 'potasio' in df_tabla.columns:
        df_tabla['potasio'] = df_tabla['potasio'].round(1)
    if 'materia_organica' in df_tabla.columns:
        df_tabla['materia_organica'] = df_tabla['materia_organica'].round(1)
    # Convertir a lista para la tabla
    table_data = [df_tabla.columns.tolist()]
    for _, row in df_tabla.iterrows():
        table_data.append(row.tolist())
    # Crear tabla
    zona_table = Table(table_data, colWidths=[0.5*inch] + [0.7*inch] * (len(columnas_tabla)-1))
    zona_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    story.append(zona_table)
    if len(gdf_analisis) > 10:
        story.append(Spacer(1, 5))
        story.append(Paragraph(f"* Mostrando 10 de {len(gdf_analisis)} zonas totales. Consulte el archivo CSV para todos los datos.", 
                             ParagraphStyle('Small', parent=normal_style, fontSize=8)))
    story.append(Spacer(1, 20))
    # Recomendaciones agroecológicas
    story.append(PageBreak())
    story.append(Paragraph("RECOMENDACIONES AGROECOLÓGICAS", heading_style))
    if analisis_tipo == "ANÁLISIS DE TEXTURA" and gdf_textura is not None:
        textura_predominante = gdf_textura['textura_suelo'].mode()[0] if len(gdf_textura) > 0 else "Franco"
        adecuacion_promedio = gdf_textura['adecuacion_textura'].mean()
        if adecuacion_promedio >= 0.8:
            enfoque = "ENFOQUE: MANTENIMIENTO - Textura adecuada"
        elif adecuacion_promedio >= 0.6:
            enfoque = "ENFOQUE: MEJORA MODERADA - Ajustes menores necesarios"
        else:
            enfoque = "ENFOQUE: MEJORA INTEGRAL - Enmiendas requeridas"
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        # Recomendaciones específicas de textura
        recomendaciones_textura = RECOMENDACIONES_TEXTURA.get(textura_predominante, [])
        story.append(Paragraph(f"<b>Recomendaciones para textura {textura_predominante}:</b>", normal_style))
        for rec in recomendaciones_textura[:4]:
            story.append(Paragraph(f"• {rec}", normal_style))
    else:
        categoria_promedio = gdf_analisis['categoria'].mode()[0] if len(gdf_analisis) > 0 else "MEDIA"
        # Determinar enfoque
        if categoria_promedio in ["MUY BAJA", "BAJA"]:
            enfoque = "ENFOQUE: RECUPERACIÓN Y REGENERACIÓN - Intensidad: Alta"
        elif categoria_promedio in ["MEDIA"]:
            enfoque = "ENFOQUE: MANTENIMIENTO Y MEJORA - Intensidad: Media"
        else:
            enfoque = "ENFOQUE: CONSERVACIÓN Y OPTIMIZACIÓN - Intensidad: Baja"
        story.append(Paragraph(f"<b>Enfoque Principal:</b> {enfoque}", normal_style))
        story.append(Spacer(1, 10))
        # Recomendaciones específicas del cultivo
        recomendaciones = RECOMENDACIONES_AGROECOLOGICAS.get(cultivo, {})
        for categoria_rec, items in recomendaciones.items():
            story.append(Paragraph(f"<b>{categoria_rec.replace('_', ' ').title()}:</b>", normal_style))
            for item in items[:3]:  # Mostrar solo 3 items por categoría
                story.append(Paragraph(f"• {item}", normal_style))
            story.append(Spacer(1, 5))
    # Plan de implementación
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>PLAN DE IMPLEMENTACIÓN:</b>", normal_style))
    planes = [
        ("INMEDIATO (0-15 días)", [
            "Preparación del terreno",
            "Siembra de abonos verdes", 
            "Aplicación de biofertilizantes"
        ]),
        ("CORTO PLAZO (1-3 meses)", [
            "Establecimiento coberturas",
            "Monitoreo inicial",
            "Ajustes de manejo"
        ]),
        ("MEDIANO PLAZO (3-12 meses)", [
            "Evaluación de resultados",
            "Diversificación",
            "Optimización del sistema"
        ])
    ]
    for periodo, acciones in planes:
        story.append(Paragraph(f"<b>{periodo}:</b>", normal_style))
        for accion in acciones:
            story.append(Paragraph(f"• {accion}", normal_style))
        story.append(Spacer(1, 5))
    # Pie de página con información adicional
    story.append(Spacer(1, 20))
    story.append(Paragraph("INFORMACIÓN ADICIONAL", heading_style))
    story.append(Paragraph("Este informe fue generado automáticamente por el Sistema de Análisis Agrícola GEE.", normal_style))
    story.append(Paragraph("Para consultas técnicas o información detallada, contacte con el departamento técnico.", normal_style))
    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    return buffer
