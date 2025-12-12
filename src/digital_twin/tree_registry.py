class TreeRegistry:
    def __init__(self):
        self.trees = {}  # {tree_id: {gps, cultivo, edad, variedad, historial}}

    def register_tree(self, tree_id: str, gps: tuple, metadata: dict):
        self.trees[tree_id] = {"gps": gps, **metadata}

    def get_tree(self, tree_id: str):
        return self.trees.get(tree_id)
