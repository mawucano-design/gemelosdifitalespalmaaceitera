import os
import requests
import json
import cv2
import numpy as np
from PIL import Image
import tempfile
import streamlit as st
from datetime import datetime

class RoboflowVisionAnalyzer:
    """Analiza imágenes agrícolas usando Roboflow API"""
    
    def __init__(self, api_key=None, project_id="palm-tree-detection", model_version=1):
        self.api_key = api_key or os.getenv('ROBOFLOW_API_KEY')
        self.project_id = project_id
        self.model_version = model_version
        self.base_url = f"https://detect.roboflow.com/{project_id}/{model_version}"
        
    def detect_palm_trees(self, image_path, confidence=0.5, overlap=30):
        """
        Detecta palmeras en una imagen usando Roboflow
        
        Args:
            image_path: Ruta a la imagen
            confidence: Umbral de confianza (0-1)
            overlap: Máximo solapamiento permitido (%)
            
        Returns:
            Lista de detecciones con coordenadas y métricas
        """
        
        # Leer imagen
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Configurar parámetros
        params = {
            'api_key': self.api_key,
            'confidence': confidence,
            'overlap': overlap,
            'format': 'json',
            'labels': True
        }
        
        try:
            # Enviar a Roboflow API
            response = requests.post(
                self.base_url,
                params=params,
                data=image_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                result = response.json()
                return self._process_roboflow_detections(result, image_path)
            else:
                st.error(f"Error API Roboflow: {response.status_code}")
                return self._create_demo_detections(image_path)
                
        except Exception as e:
            st.warning(f"Error conectando con Roboflow: {str(e)}")
            return self._create_demo_detections(image_path)
    
    def _process_roboflow_detections(self, api_result, image_path):
        """Procesa resultados de Roboflow API"""
        
        detections = []
        
        # Leer imagen para obtener dimensiones
        img = cv2.imread(image_path)
        if img is None:
            img = Image.open(image_path)
            height, width = img.size[1], img.size[0]
        else:
            height, width = img.shape[:2]
        
        # Procesar cada detección
        for pred in api_result.get('predictions', []):
            detection = {
                'class': pred.get('class', 'palm_tree'),
                'confidence': float(pred.get('confidence', 0)),
                'bbox': {
                    'x': float(pred.get('x', 0)),
                    'y': float(pred.get('y', 0)),
                    'width': float(pred.get('width', 0)),
                    'height': float(pred.get('height', 0))
                },
                'pixel_coords': {
                    'center_x': float(pred.get('x', 0)) * width / 100,
                    'center_y': float(pred.get('y', 0)) * height / 100,
                    'width_px': float(pred.get('width', 0)) * width / 100,
                    'height_px': float(pred.get('height', 0)) * height / 100
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # Calcular coordenadas de bounding box
            x_center = detection['pixel_coords']['center_x']
            y_center = detection['pixel_coords']['center_y']
            w = detection['pixel_coords']['width_px']
            h = detection['pixel_coords']['height_px']
            
            detection['bbox_coords'] = {
                'x1': x_center - w/2,
                'y1': y_center - h/2,
                'x2': x_center + w/2,
                'y2': y_center + h/2
            }
            
            detections.append(detection)
        
        st.success(f"✅ Detectadas {len(detections)} palmeras")
        return detections
    
    def _create_demo_detections(self, image_path):
        """Crea detecciones de demostración (para desarrollo)"""
        
        # Leer imagen para dimensiones
        img = Image.open(image_path)
        width, height = img.size
        
        # Generar detecciones simuladas
        detections = []
        num_trees = np.random.randint(30, 60)
        
        for i in range(num_trees):
            # Coordenadas aleatorias pero evitando bordes
            x_center = np.random.randint(50, width - 50)
            y_center = np.random.randint(50, height - 50)
            
            # Tamaño variable
            tree_width = np.random.randint(30, 80)
            tree_height = np.random.randint(40, 100)
            
            # Confianza simulada
            confidence = np.random.uniform(0.7, 0.95)
            
            detection = {
                'class': 'palm_tree',
                'confidence': confidence,
                'bbox': {
                    'x': x_center * 100 / width,
                    'y': y_center * 100 / height,
                    'width': tree_width * 100 / width,
                    'height': tree_height * 100 / height
                },
                'pixel_coords': {
                    'center_x': x_center,
                    'center_y': y_center,
                    'width_px': tree_width,
                    'height_px': tree_height
                },
                'bbox_coords': {
                    'x1': x_center - tree_width/2,
                    'y1': y_center - tree_height/2,
                    'x2': x_center + tree_width/2,
                    'y2': y_center + tree_height/2
                },
                'timestamp': datetime.now().isoformat(),
                'is_demo': True
            }
            
            detections.append(detection)
        
        st.info(f"🧪 Modo demo: {len(detections)} palmeras simuladas")
        return detections
    
    def analyze_tree_health(self, image_path, detections):
        """
        Analiza salud de cada palmera detectada
        
        Args:
            image_path: Ruta a la imagen
            detections: Lista de detecciones de palmeras
            
        Returns:
            Detecciones enriquecidas con análisis de salud
        """
        
        img = cv2.imread(image_path)
        if img is None:
            return detections
        
        # Convertir a HSV para análisis de color
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        for det in detections:
            # Recortar región del árbol
            x1, y1 = int(det['bbox_coords']['x1']), int(det['bbox_coords']['y1'])
            x2, y2 = int(det['bbox_coords']['x2']), int(det['bbox_coords']['y2'])
            
            # Asegurar coordenadas dentro de la imagen
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
            
            if x2 > x1 and y2 > y1:
                # Recortar región
                tree_roi = img[y1:y2, x1:x2]
                hsv_roi = hsv[y1:y2, x1:x2]
                
                # Métricas simples de salud (en un sistema real sería más complejo)
                health_score = self._calculate_tree_health(tree_roi, hsv_roi)
                
                # Clasificar salud
                if health_score >= 0.7:
                    health_status = "EXCELENTE"
                    color = "🟢"
                elif health_score >= 0.5:
                    health_status = "BUENA"
                    color = "🟡"
                elif health_score >= 0.3:
                    health_status = "MODERADA"
                    color = "🟠"
                else:
                    health_status = "CRÍTICA"
                    color = "🔴"
                
                det['health'] = {
                    'score': health_score,
                    'status': health_status,
                    'color': color,
                    'canopy_area': (x2 - x1) * (y2 - y1),
                    'dominant_color': self._get_dominant_color(hsv_roi)
                }
            else:
                # Valores por defecto si no se puede recortar
                det['health'] = {
                    'score': 0.5,
                    'status': "DESCONOCIDA",
                    'color': "⚫",
                    'canopy_area': 0,
                    'dominant_color': "N/A"
                }
        
        return detections
    
    def _calculate_tree_health(self, rgb_roi, hsv_roi):
        """Calcula un score de salud basado en características de color"""
        
        if rgb_roi.size == 0:
            return 0.5
        
        # 1. Verde dominante (canal H en HSV)
        green_mask = cv2.inRange(hsv_roi, (36, 25, 25), (86, 255, 255))
        green_percentage = np.sum(green_mask > 0) / green_mask.size
        
        # 2. Vitalidad (saturación promedio)
        mean_saturation = np.mean(hsv_roi[:, :, 1]) / 255
        
        # 3. Brillo adecuado (no muy oscuro, no muy brillante)
        mean_value = np.mean(hsv_roi[:, :, 2]) / 255
        brightness_score = 1 - abs(mean_value - 0.5) * 2  # Ideal alrededor de 0.5
        
        # Ponderar scores
        health_score = (
            green_percentage * 0.5 +
            mean_saturation * 0.3 +
            brightness_score * 0.2
        )
        
        return float(health_score)
    
    def _get_dominant_color(self, hsv_roi):
        """Obtiene el color dominante en la región"""
        
        if hsv_roi.size == 0:
            return "N/A"
        
        # Calcular histograma del canal Hue
        hist = cv2.calcHist([hsv_roi], [0], None, [180], [0, 180])
        dominant_hue = np.argmax(hist)
        
        # Clasificar por rango de Hue
        if 36 <= dominant_hue <= 86:
            return "VERDE"
        elif 20 <= dominant_hue <= 35:
            return "AMARILLO-VERDE"
        elif 0 <= dominant_hue <= 19 or 160 <= dominant_hue <= 180:
            return "ROJO-MARRÓN"
        elif 87 <= dominant_hue <= 140:
            return "VERDE-AZULADO"
        else:
            return "OTRO"
    
    def create_visualization(self, image_path, detections, output_path=None):
        """
        Crea visualización con bounding boxes y etiquetas
        
        Args:
            image_path: Ruta a imagen original
            detections: Lista de detecciones
            output_path: Ruta para guardar (opcional)
            
        Returns:
            Ruta a imagen visualizada
        """
        
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        # Colores por estado de salud
        color_map = {
            "EXCELENTE": (0, 255, 0),    # Verde
            "BUENA": (255, 255, 0),      # Amarillo
            "MODERADA": (255, 165, 0),   # Naranja
            "CRÍTICA": (255, 0, 0),      # Rojo
            "DESCONOCIDA": (128, 128, 128) # Gris
        }
        
        for det in detections:
            health_status = det.get('health', {}).get('status', 'DESCONOCIDA')
            color = color_map.get(health_status, (128, 128, 128))
            
            # Coordenadas del bounding box
            x1 = int(det['bbox_coords']['x1'])
            y1 = int(det['bbox_coords']['y1'])
            x2 = int(det['bbox_coords']['x2'])
            y2 = int(det['bbox_coords']['y2'])
            
            # Dibujar bounding box
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            
            # Etiqueta con confianza
            label = f"{health_status} ({det['confidence']:.1%})"
            
            # Fondo para texto
            (text_width, text_height), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            
            cv2.rectangle(img, (x1, y1 - 20), 
                         (x1 + text_width, y1), color, -1)
            
            # Texto
            cv2.putText(img, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Añadir contador total
        total_trees = len(detections)
        cv2.putText(img, f"Total: {total_trees} palmeras", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Guardar o retornar
        if output_path:
            cv2.imwrite(output_path, img)
            return output_path
        else:
            # Guardar temporalmente
            temp_path = tempfile.mktemp(suffix='.jpg')
            cv2.imwrite(temp_path, img)
            return temp_path

def test_roboflow_integration(image_path):
    """Prueba la integración con Roboflow"""
    
    analyzer = RoboflowVisionAnalyzer()
    
    st.info("🌴 Detectando palmeras con Roboflow API...")
    detections = analyzer.detect_palm_trees(image_path)
    
    if detections:
        # Analizar salud
        detections_with_health = analyzer.analyze_tree_health(image_path, detections)
        
        # Crear visualización
        viz_path = analyzer.create_visualization(
            image_path, 
            detections_with_health,
            output_path="./data/vision/detection_result.jpg"
        )
        
        # Mostrar estadísticas
        health_stats = {}
        for det in detections_with_health:
            status = det['health']['status']
            health_stats[status] = health_stats.get(status, 0) + 1
        
        st.success("📊 Estadísticas de salud:")
        for status, count in health_stats.items():
            st.write(f"- {status}: {count} árboles")
        
        return detections_with_health, viz_path
    
    return [], None
