from setuptools import setup, find_packages

setup(
    name="gemelos-digitales-palma",
    version="1.0.0",
    author="Tu Nombre",
    description="Aplicación de análisis agrícola con GEE y agroecología",
    packages=find_packages(),
    install_requires=[
        "streamlit>=1.32.0",
        "geopandas>=0.14.0",
        "pandas>=2.0.0",
        "numpy>=1.26.0",
        "matplotlib>=3.7.0",
        "folium>=0.14.0",
        "streamlit-folium>=0.15.1",
        "shapely>=2.0.0",
        "reportlab>=4.0.0",
        "Pillow>=10.0.0",
        "fiona>=1.9.0",
    ],
    python_requires=">=3.9",
)
