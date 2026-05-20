"""
Définitions des attributs à extraire pour les documents de type "kbis".
"""

from .common import (
    ACTIVITE_PRINCIPALE,
    ADRESSE_POSTALE_INSEE,
    DENOMINATION,
    SIREN,
)

KBIS_ATTRIBUTES = {
    "denomination": DENOMINATION,
    "siren": SIREN,
    "activite_principale": ACTIVITE_PRINCIPALE,
    "adresse_postale_insee": ADRESSE_POSTALE_INSEE,
}
