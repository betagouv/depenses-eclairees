# Import des dictionnaires d'attributs depuis les fichiers séparés
from .attributes import (
    ACTE_ENGAGEMENT_ATTRIBUTES,
    ATT_SIRENE_ATTRIBUTES,
    AVENANT_ATTRIBUTES,
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
# Types additionnels réutilisent les prompts d'un type "canonique" (même dict d'attributs).
DOC_TYPE_ATTRIBUTES_MAPPING = {
    "acte_engagement": ACTE_ENGAGEMENT_ATTRIBUTES,
    "avenant": AVENANT_ATTRIBUTES,
    "att_sirene": ATT_SIRENE_ATTRIBUTES,
    "bon_de_commande": BON_DE_COMMANDE_ATTRIBUTES,
    "ccap": CCAP_ATTRIBUTES,
    "ccp_simple": CCAP_ATTRIBUTES,
    "ccp_vae": ACTE_ENGAGEMENT_ATTRIBUTES,
    "conv_financement": AVENANT_ATTRIBUTES,
    "cctp": CCTP_ATTRIBUTES,
    "devis": DEVIS_ATTRIBUTES,
    "facture": DEVIS_ATTRIBUTES,
    "fiche_navette": FICHE_NAVETTE_ATTRIBUTES,
    "kbis": KBIS_ATTRIBUTES,
    "rib": RIB_ATTRIBUTES,
    "sous_traitance": SOUS_TRAITANCE_ATTRIBUTES,
}


DOC_TYPE_SCHEMA_MAPPING = {}

for doc_type, attributes in DOC_TYPE_ATTRIBUTES_MAPPING.items():
    doc_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    for attribute_key, attribute_definition in attributes.items():
        attribute_schema = attribute_definition.get("schema", {"type": "string"})
        doc_schema["properties"][attribute_key] = attribute_schema
        doc_schema["required"].append(attribute_key)
    DOC_TYPE_SCHEMA_MAPPING[doc_type] = doc_schema

# Génère le DataFrame ATTRIBUTES à partir des fichiers séparés
rows = []
for doc_type, attributes_dict in DOC_TYPE_ATTRIBUTES_MAPPING.items():
    for attr_name, attr_def in attributes_dict.items():
        rows.append(
            {
                "attribut": attr_name,
                "consigne": attr_def.get("consigne", None),
                "schema": attr_def.get("schema", None),
                "type_attachments": [doc_type],  # Chaque attribut est associé à son type de document
            }
        )
