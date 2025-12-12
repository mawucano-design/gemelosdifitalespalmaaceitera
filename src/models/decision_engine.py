def generate_agro_recommendation(tree_data: dict, parcela_context: dict):
    """
    STUB: Motor de decisiones con RAG o reglas.
    Combina estado del árbol + fertilidad + textura + pronóstico.
    """
    return {
        "action": "aplicar_nitrogeno",
        "dosis_kg_ha": 45,
        "urgencia": "alta",
        "justificacion": "NDVI bajo + N actual < óptimo"
    }
