"""
Module contenant la classe Tiers pour représenter les entités tierces.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class Tiers:
    """
    Classe représentant une entité tierce (entreprise, organisation, etc.).
    
    Attributes:
        denomination (str): Dénomination de l'entité
        siret (Optional[str]): Numéro SIRET de l'entité
        siren (Optional[str]): Numéro SIREN de l'entité
        iban (Optional[str]): Code IBAN de l'entité
        bic (Optional[str]): Code BIC de l'entité
        domiciliation (Optional[str]): Domiciliation de l'entité
        num_tiers (Optional[str]): Numéro de tiers dans le système
        activite_principale (Optional[str]): Activité principale de l'entité
        adresse_postale (Optional[str]): Adresse postale complète
        montant_sous_traitance (Optional[float]): Montant de sous-traitance en euros
    """
    
    denomination: str
    siret: Optional[str] = None
    siren: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    domiciliation: Optional[str] = None
    num_tiers: Optional[str] = None
    activite_principale: Optional[str] = None
    adresse_postale: Optional[str] = None
    montant_sous_traitance: Optional[str] = None

    def __str__(self) -> str:
        """Représentation string de l'objet Tiers."""
        return f"Tiers(denomination='{self.denomination}', siret='{self.siret}')"

    def __repr__(self) -> str:
        """Représentation détaillée de l'objet Tiers avec toutes les caractéristiques."""
        return (
            f"Tiers(denomination='{self.denomination}', "
            f"siret='{self.siret}', "
            f"siren='{self.siren}', "
            f"iban='{self.iban}', "
            f"bic='{self.bic}', "
            f"domiciliation='{self.domiciliation}', "
            f"num_tiers='{self.num_tiers}', "
            f"activite_principale='{self.activite_principale}', "
            f"adresse_postale='{self.adresse_postale}', "
            f"montant_sous_traitance='{self.montant_sous_traitance}')"
        )
    
    def to_dict(self) -> dict:
        """Convertit l'objet Tiers en dictionnaire."""
        return {
            'denomination': self.denomination,
            'siret': self.siret,
            'siren': self.siren,
            'iban': self.iban,
            'bic': self.bic,
            'domiciliation': self.domiciliation,
            'num_tiers': self.num_tiers,
            'activite_principale': self.activite_principale,
            'adresse_postale': self.adresse_postale,
            'montant_sous_traitance': self.montant_sous_traitance
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Tiers':
        """Crée un objet Tiers à partir d'un dictionnaire."""
        return cls(**data)
