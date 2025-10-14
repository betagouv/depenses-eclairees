"""
Module contenant la classe Marché pour représenter les marchés publics.
"""

from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime, date
from .tiers import Tiers


@dataclass
class Marche:
    """
    Classe représentant un marché public.
    
    Attributes:
        objet (str): Objet du marché
        montant_maximum (Optional[float]): Montant maximum du marché en euros
        duree (Optional[int]): Durée du marché en mois
        date_notification (Optional[date]): Date de notification du marché
        date_fin (Optional[date]): Date de fin du marché
        numero_ej (Optional[str]): Numéro d'engagement juridique
        numero_long (Optional[str]): Numéro long du marché
        titulaire (Optional[Tiers]): Titulaire du marché
        sous_traitants (List[Tiers]): Liste des sous-traitants
        co_traitants (List[Tiers]): Liste des co-traitants
        pouvoir_adjudicateur (Optional[str]): Pouvoir adjudicateur
        variation_prix (Optional[str]): Variation des prix (ex: "Ferme", "Révisable")
        forme_prix (Optional[str]): Forme des prix (ex: "Global", "Unitaire", "Mixte")
    """
    
    objet: str
    montant_maximum: Optional[float] = None
    duree: Optional[int] = None
    date_notification: Optional[date] = None
    date_fin: Optional[date] = None
    numero_ej: Optional[str] = None
    numero_long: Optional[str] = None
    titulaire: Optional[Tiers] = None
    sous_traitants: List[Tiers] = field(default_factory=list)
    co_traitants: List[Tiers] = field(default_factory=list)
    pouvoir_adjudicateur: Optional[str] = None
    variation_prix: Optional[str] = None
    forme_prix: Optional[str] = None
    
    def __str__(self) -> str:
        """Représentation string de l'objet Marché."""
        return f"Marché(objet='{self.objet}', montant_max={self.montant_maximum}, EJ={self.numero_ej})"
    
    def __repr__(self) -> str:
        """Représentation détaillée de l'objet Marché."""
        return (f"Marché(objet='{self.objet}', montant_max={self.montant_maximum}, "
                f"duree={self.duree}, numero_ej='{self.numero_ej}', "
                f"numero_long='{self.numero_long}')")
    
    def ajouter_sous_traitant(self, sous_traitant: Tiers) -> None:
        """Ajoute un sous-traitant à la liste."""
        if sous_traitant not in self.sous_traitants:
            self.sous_traitants.append(sous_traitant)
    
    def ajouter_co_traitant(self, co_traitant: Tiers) -> None:
        """Ajoute un co-traitant à la liste."""
        if co_traitant not in self.co_traitants:
            self.co_traitants.append(co_traitant)
    
    def retirer_sous_traitant(self, sous_traitant: Tiers) -> bool:
        """Retire un sous-traitant de la liste. Retourne True si retiré, False sinon."""
        try:
            self.sous_traitants.remove(sous_traitant)
            return True
        except ValueError:
            return False
    
    def retirer_co_traitant(self, co_traitant: Tiers) -> bool:
        """Retire un co-traitant de la liste. Retourne True si retiré, False sinon."""
        try:
            self.co_traitants.remove(co_traitant)
            return True
        except ValueError:
            return False
    
    def get_duree_en_jours(self) -> Optional[int]:
        """Calcule la durée du marché en jours si les dates sont disponibles."""
        if self.date_notification and self.date_fin:
            return (self.date_fin - self.date_notification).days
        return None
    
    def est_en_cours(self, date_reference: Optional[date] = None) -> bool:
        """Vérifie si le marché est en cours à une date donnée."""
        if date_reference is None:
            date_reference = date.today()
        
        if not self.date_notification or not self.date_fin:
            return False
        
        return self.date_notification <= date_reference <= self.date_fin
    
    def to_dict(self) -> dict:
        """Convertit l'objet Marché en dictionnaire."""
        return {
            'objet': self.objet,
            'montant_maximum': self.montant_maximum,
            'duree': self.duree,
            'date_notification': self.date_notification.isoformat() if self.date_notification else None,
            'date_fin': self.date_fin.isoformat() if self.date_fin else None,
            'numero_ej': self.numero_ej,
            'numero_long': self.numero_long,
            'titulaire': self.titulaire.to_dict() if self.titulaire else None,
            'sous_traitants': [st.to_dict() for st in self.sous_traitants],
            'co_traitants': [ct.to_dict() for ct in self.co_traitants],
            'pouvoir_adjudicateur': self.pouvoir_adjudicateur,
            'variation_prix': self.variation_prix,
            'forme_prix': self.forme_prix
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Marche':
        """Crée un objet Marché à partir d'un dictionnaire."""
        # Conversion des dates
        date_notification = None
        if data.get('date_notification'):
            date_notification = datetime.fromisoformat(data['date_notification']).date()
        
        date_fin = None
        if data.get('date_fin'):
            date_fin = datetime.fromisoformat(data['date_fin']).date()
        
        # Conversion du titulaire
        titulaire = None
        if data.get('titulaire'):
            titulaire = Tiers.from_dict(data['titulaire'])
        
        # Conversion des sous-traitants
        sous_traitants = []
        if data.get('sous_traitants'):
            sous_traitants = [Tiers.from_dict(st) for st in data['sous_traitants']]
        
        # Conversion des co-traitants
        co_traitants = []
        if data.get('co_traitants'):
            co_traitants = [Tiers.from_dict(ct) for ct in data['co_traitants']]
        
        return cls(
            objet=data['objet'],
            montant_maximum=data.get('montant_maximum'),
            duree=data.get('duree'),
            date_notification=date_notification,
            date_fin=date_fin,
            numero_ej=data.get('numero_ej'),
            numero_long=data.get('numero_long'),
            titulaire=titulaire,
            sous_traitants=sous_traitants,
            co_traitants=co_traitants,
            pouvoir_adjudicateur=data.get('pouvoir_adjudicateur'),
            variation_prix=data.get('variation_prix'),
            forme_prix=data.get('forme_prix')
        )
