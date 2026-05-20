"""
Définitions des attributs à extraire pour les documents de type "att_sirene".
"""

from .common import (
    ACTIVITE_PRINCIPALE,
    ADRESSE_POSTALE_INSEE,
    DENOMINATION,
    SIREN,
    SIRET,
)

ATT_SIRENE_ATTRIBUTES = {
    "siret": SIRET,
    "siren": SIREN,
    "denomination": DENOMINATION,
    "activite_principale": ACTIVITE_PRINCIPALE,
    "adresse_postale_insee": ADRESSE_POSTALE_INSEE,
}
