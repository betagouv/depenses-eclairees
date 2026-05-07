"""
Définitions des attributs à extraire pour les documents de type "kbis".
"""

KBIS_ATTRIBUTES = {
    "denomination": {
        "consigne": """
     Définition : Dénomination de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher la dénomination de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune dénomination trouvée.
""",
    },
    "siren": {
        "consigne": """
      Définition : Numéro SIREN de la personne morale dans l'extrait Kbis.
      Indices : 
      - Rechercher le numéro SIREN de la personne morale dans l'extrait Kbis.
      - A partir d'un numéro RCS : les 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
      - Ne rien renvoyer si aucun numéro SIREN trouvé.
""",
    },
    "activite_principale": {
        "consigne": """
     Définition : Activité principale exercée (APE) de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher l'activité principale de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune activité principale trouvée.
""",
    },
    "adresse_postale_insee": {
        "consigne": """
     Définition : Adresse postale de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher l'adresse postale de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune adresse postale trouvée.
""",
    },
}
