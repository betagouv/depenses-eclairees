"""
Définitions des attributs à extraire pour les documents de type "bon_de_commande".
"""

from .common import (
    ADMINISTRATION_BENEFICIAIRE,
    DATE_SIGNATURE,
    DESCRIPTION_PRESTATIONS,
    MONTANT_HT,
    MONTANT_TTC,
    OBJET,
    SIREN,
    SIRET,
    SOCIETE_PRINCIPALE,
)

BON_DE_COMMANDE_ATTRIBUTES = {
    "objet": OBJET,
    "type_document": {
        "consigne": """
   Définition : catégorie juridique ou administrative du document.
   Indices :
   - Le type de document est souvent mentionné au début du document dans le titre ou le sous-titre.
   - Exemples de types de documents : devis, acte d'engagement, avenant, bon de commande, cachier des charges, ...
   - Ne rien renvoyer si aucun type de document trouvé
   Format : en minuscule, sans accent, sans espace (ex: "devis", "acte_engagement", "bon_de_commande")
""",
    },
    "montant_ht": MONTANT_HT,
    "montant_ttc": MONTANT_TTC,
    "administration_beneficiaire": ADMINISTRATION_BENEFICIAIRE,
    "description_prestations": DESCRIPTION_PRESTATIONS,
    "date_signature": DATE_SIGNATURE,
    "societe_principale": SOCIETE_PRINCIPALE,
    "siren": SIREN,
    "siret": SIRET,
}
