import uuid
from datetime import datetime

class TreeRegistry:
    def __init__(self):
        self.trees = {}

    def register_trees_from_boxes(self, boxes, parcela_id: str):
        trees = []
        for i, box in enumerate(boxes):
            tree_id = f"{parcela_id}_tree_{i+1}"
            self.trees[tree_id] = {
                "id": tree_id,
                "detection_bbox": box,
                "parcela_id": parcela_id,
                "fecha_registro": datetime.now().isoformat(),
                "estado_actual": "activo"
            }
            trees.append(tree_id)
        return trees
