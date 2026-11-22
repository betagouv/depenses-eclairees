"""Libellés lisibles pour l'UI classify (hors Django / classifier)."""

from __future__ import annotations

# Aligné sur COARSE_LABELS + libellés produit quand ils existent
DISPLAY_BY_LABEL: dict[str, str] = {
    "acte_engagement": "Acte d'engagement",
    "annexe": "Annexe",
    "catalogue_prix": "Catalogue de prix",
    "devis": "Devis",
    "ccap": "CCAP",
    "cctp": "CCTP",
    "avenant": "Avenant",
    "sous_traitance": "Sous-traitance",
    "rib": "RIB",
    "contrats_mixte": "Contrats mixte",
    "messagerie": "Messagerie",
    "fiche_navette": "Fiche navette",
    "outil_gestion": "Outil de gestion",
    "execution_commande": "Exécution de commande",
    "certificats_administratifs": "Certificats administratifs",
    "dossier_candidature": "Dossier de candidature",
    "consultation_marche": "Consultation de marché",
    "bordereau_prix": "Bordereau de prix",
    "detail_quantitatif_estimatif": "DQE",
}


def display_name_for_label(label: str) -> str:
    if not label:
        return label
    mapped = DISPLAY_BY_LABEL.get(label)
    if mapped:
        return mapped
    return label.replace("_", " ").title()