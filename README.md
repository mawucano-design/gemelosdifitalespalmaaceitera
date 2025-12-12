# 🌱 Aplicación de Análisis Agrícola con Metodología GEE y Agroecología

Aplicación web para análisis de fertilidad y recomendaciones NPK en cultivos de palma aceitera, cacao y banano, utilizando metodología GEE (Google Earth Engine) y principios agroecológicos.

## 🚀 Características Principales

### 🌿 **Análisis por Cultivo**
- **Palma Aceitera**: Recomendaciones específicas para plantaciones
- **Cacao**: Análisis para sistemas agroforestales
- **Banano**: Optimización para cultivos de alta densidad

### 📊 **Tipos de Análisis**
1. **Fertilidad Actual**: Índice NPK, materia orgánica, pH, humedad
2. **Recomendaciones NPK**: Dosis específicas por nutriente (N, P, K)
3. **Análisis de Textura**: Clasificación USDA, propiedades físicas del suelo

### 🗺️ **Funcionalidades Geoespaciales**
- Carga de shapefiles y archivos KML
- División en zonas de manejo (16-32 zonas)
- Mapas interactivos con ESRI Satellite
- Visualización de resultados por zona

### 🌍 **Metodología GEE Integrada**
- Simulación de análisis con Google Earth Engine
- Índices espectrales (NDVI) y modelos predictivos
- Factores estacionales y espaciales
- Análisis de variabilidad espacial

### ♻️ **Enfoque Agroecológico**
- Recomendaciones de coberturas vivas
- Abonos verdes y biofertilizantes
- Manejo ecológico de plagas
- Asociaciones y diversificación de cultivos

## 🗺️ Hoja de Ruta: Hacia el Digital Twin por Árbol

Esta aplicación está diseñada para evolucionar desde zonas de manejo hacia un gemelo digital **por árbol**, siguiendo el enfoque del artículo de LinkedIn:

- **Fase 1 (Actual)**: Análisis por zonas con simulación GEE y agroecología.
- **Fase 2**: Integración con datos reales de drones (multiespectral) y detección de árboles (CV).
- **Fase 3**: Motor de decisiones con IA generativa (RAG) y recomendaciones dinámicas.
- **Fase 4**: Sincronización con ERP (SAP/mySAP365) para operaciones del campo.
- **Fase 5**: Digital Twin vivo por árbol, con historial, sensores y alertas predictivas.

## 📦 Instalación

### Requisitos Previos
- Python 3.9 o superior
- GDAL (para procesamiento geoespacial)

### Instalación Local

## 🚀 Despliegue en Streamlit Cloud

1. **Sube a GitHub:**
   ```bash
   git add .
   git commit -m "Initial app deployment"
   git push origin main
