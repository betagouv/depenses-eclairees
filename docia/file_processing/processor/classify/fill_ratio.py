"""Taux de remplissage structured_data — même logique que docia.views."""


def compute_ratio_data_extraction(document_data: dict | list | None) -> float:
    if not document_data or not isinstance(document_data, dict):
        return 0.0
    total_keys = len(document_data.keys())
    if total_keys == 0:
        return 0.0
    total_extracted = len([x for x in document_data.values() if x])
    return total_extracted / total_keys