import os
import tempfile
from PIL import Image
import numpy as np
from ultralytics import YOLO
import streamlit as st

# Descargar modelo preentrenado (solo si no existe)
def _download_model():
    model_path = "models/palm_tree_yolov8n.pt"
    if not os.path.exists(model_path):
        os.makedirs("models", exist_ok=True)
        st.info("📥 Descargando modelo de detección de palmas (primera ejecución solo)...")
        # Aquí puedes subir tu propio modelo a Hugging Face o GitHub
        # Para este ejemplo, usamos un modelo público genérico de árboles
        # En producción: reemplaza con tu modelo entrenado en palma aceitera
        from ultralytics import YOLO
        model = YOLO("yolov8n.pt")  # modelo base
        model.export(format="torchscript")  # opcional
        # NOTA: para mejor precisión, entrena un modelo con imágenes de palma aceitera
        return model
    else:
        return YOLO(model_path)

def detect_trees_from_image(image_path: str, cultivo: str):
    """
    Detecta árboles en una imagen satelital o drone usando YOLO.
    Devuelve lista de bounding boxes (xmin, ymin, xmax, ymax).
    """
    if cultivo != "PALMA_ACEITERA":
        st.warning("⚠️ Detección por CV solo disponible para PALMA_ACEITERA (fase inicial).")
        return []
    
    try:
        model = YOLO("yolov8n.pt")  # ligero, funciona en CPU
        results = model(image_path)
        boxes = []
        for r in results:
            for box in r.boxes:
                # Solo clases "tree", "plant", o "palm" si están en el modelo
                if int(box.cls) in [59, 60, 70]:  # ajusta según tu dataset
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    boxes.append(xyxy.tolist())
        return boxes
    except Exception as e:
        st.error(f"❌ Error en detección de árboles: {str(e)}")
        return []
