import pandas as pd

# Import des dictionnaires d'attributs depuis les fichiers séparés
from .attributes import (
    ACTE_ENGAGEMENT_ATTRIBUTES,
    AVENANT_ATTRIBUTES,
    ATT_SIRENE_ATTRIBUTES,
    BON_DE_COMMANDE_ATTRIBUTES,
    CCAP_ATTRIBUTES,
    CCTP_ATTRIBUTES,
    DEVIS_ATTRIBUTES,
    FICHE_NAVETTE_ATTRIBUTES,
    KBIS_ATTRIBUTES,
    RIB_ATTRIBUTES,
    SOUS_TRAITANCE_ATTRIBUTES,
)

# Mapping entre le type de document et son dictionnaire d'attributs
DOC_TYPE_ATTRIBUTES_MAPPING = {
    "acte_engagement": ACTE_ENGAGEMENT_ATTRIBUTES,
    "avenant": AVENANT_ATTRIBUTES,
    "att_sirene": ATT_SIRENE_ATTRIBUTES,
    "bon_de_commande": BON_DE_COMMANDE_ATTRIBUTES,
    "ccap": CCAP_ATTRIBUTES,
    "cctp": CCTP_ATTRIBUTES,
    "devis": DEVIS_ATTRIBUTES,
    "fiche_navette": FICHE_NAVETTE_ATTRIBUTES,
    "kbis": KBIS_ATTRIBUTES,
    "rib": RIB_ATTRIBUTES,
    "sous_traitance": SOUS_TRAITANCE_ATTRIBUTES,
}

# Génère le DataFrame ATTRIBUTES à partir des fichiers séparés
rows = []
for doc_type, attributes_dict in DOC_TYPE_ATTRIBUTES_MAPPING.items():
    for attr_name, attr_def in attributes_dict.items():
        rows.append({
            "attribut": attr_name,
            "consigne": attr_def.get("consigne", ""),
            "search": attr_def.get("search", ""),
            "output_field": attr_def.get("output_field", attr_name),
            "schema": attr_def.get("schema", ""),
            "type_attachments": [doc_type]  # Chaque attribut est associé à son type de document
        })

ATTRIBUTES = pd.DataFrame(rows)


def select_attr(df_attributes, doc_type):
    """
    Sélectionne les lignes du DataFrame ATTRIBUTES correspondant à un type de document donné.
    Args:
        df_attributes (pd.DataFrame): DataFrame des attributs (avec colonne 'type_attachments')
        doc_type (str): Type de document à filtrer (ex: 'devis', 'cctp', ...)
    Returns:
        pd.DataFrame: Sous-ensemble du DataFrame avec les attributs du type demandé
    """
    return df_attributes[df_attributes['type_attachments'].apply(lambda types: doc_type in types)]
