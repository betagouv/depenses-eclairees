"""
Module contenant les définitions d'attributs par type de document.
"""

from .acte_engagement import ACTE_ENGAGEMENT_ATTRIBUTES
from .avenant import AVENANT_ATTRIBUTES
from .bon_de_commande import BON_DE_COMMANDE_ATTRIBUTES
from .cctp import CCTP_ATTRIBUTES
from .ccap import CCAP_ATTRIBUTES
from .devis import DEVIS_ATTRIBUTES
from .fiche_navette import FICHE_NAVETTE_ATTRIBUTES
from .kbis import KBIS_ATTRIBUTES
from .rib import RIB_ATTRIBUTES
from .sous_traitance import SOUS_TRAITANCE_ATTRIBUTES
from .att_sirene import ATT_SIRENE_ATTRIBUTES

__all__ = [
    "ACTE_ENGAGEMENT_ATTRIBUTES",
    "AVENANT_ATTRIBUTES",
    "BON_DE_COMMANDE_ATTRIBUTES",
    "CCTP_ATTRIBUTES",
    "CCAP_ATTRIBUTES",
    "DEVIS_ATTRIBUTES",
    "FICHE_NAVETTE_ATTRIBUTES",
    "KBIS_ATTRIBUTES",
    "RIB_ATTRIBUTES",
    "SOUS_TRAITANCE_ATTRIBUTES",
    "ATT_SIRENE_ATTRIBUTES",
]

