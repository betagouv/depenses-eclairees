"""
Définitions des attributs à extraire pour les documents de type "rib".
"""

from .common import ADRESSE_POSTALE_TITULAIRE

RIB_ATTRIBUTES = {
    "iban": {
        "consigne": """
     Définition : Identifiant international de compte bancaire (IBAN)
     Indices : 
     - Généralement composé de 27 caractères (pour un RIB Français), commençant souvent par "FR" pour un IBAN en France (souvent "FR76 ...", "FR09 ..." ou autres)
     - Souvent 6 groupes de 4 caractères, puis 3 caractères.
     - Si aucun IBAN trouvé, renvoyer ''
     Format : l'IBAN d'entre 21 et 27 caractères (27 si commence par FR) caractères avec espaces tous les 4 caractères (6 groupes de 4 et un groupe de 3)
""",
    },
    "code_pays": {
        "consigne": """
     Définition : Code pays de l'IBAN.
     Indices : 
     - Rechercher le code pays de l'IBAN.
     - Ne rien renvoyer si aucun code pays trouvé.
     Format : le code pays de 2 caractères (souvent FR pour la France mais peut être d'autres codes).
""",
    },
    "code_banque": {
        "consigne": """
     Définition : Code de la banque de l'IBAN.
     Indices : 
     - Rechercher le code de la banque de l'IBAN.
     - Ne rien renvoyer si aucun code de banque trouvé.
     Format : le code de la banque de 5 caractères.
""",
    },
    "code_guichet": {
        "consigne": """
     Définition : Code du guichet de l'IBAN.
     Indices : 
     - Rechercher le code du guichet de l'IBAN.
     - Ne rien renvoyer si aucun code de guichet trouvé.
     Format : le code du guichet de 5 caractères.
""",
    },
    "numero_compte": {
        "consigne": """
     Définition : Numéro de compte de l'IBAN.
     Indices : 
     - Rechercher le numéro de compte de l'IBAN.
     - Ne rien renvoyer si aucun numéro de compte trouvé.
     Format : le numéro de compte de 11 caractères.
""",
    },
    "cle_rib": {
        "consigne": """
     Définition : Clé du RIB de l'IBAN.
     Indices : 
     - Rechercher la clé du RIB de l'IBAN.
     - Ne rien renvoyer si aucune clé trouvée.
     Format : la clé du RIB de 2 caractères.
""",
    },
    "bic": {
        "consigne": """
     Définition : Code d'identification bancaire (BIC), généralement composé de 8 ou 11 caractères alphanumériques.
     Indices : 
     - Repérer les codes sous la forme "BIC" ou "Code BIC", souvent présents dans un RIB.
     - Chercher dans la section du RIB ou dans un tableau récapitulatif des coordonnées bancaires.
     - Ne rien renvoyer si aucun BIC n'est clairement identifié.
     Format : le BIC de 8 ou 11 caractères avec espaces tous les 4 caractères
""",
    },
    "titulaire_compte": {
        "consigne": """
     Définition : Nom du titulaire du compte bancaire (personne physique ou morale).
     Indices : 
     - Rechercher le nom du titulaire (personne physique ou morale)du compte bancaire dans la section du RIB.
     - S'il s'agit d'une personne morale, renvoyer le nom de la société ou de l'établissement.
        * Pas besoin de renvoyer d'informations sur la direction ou du service interne de la société titulaire.
        * Pas besoin de renvoyer d'informations autres que le nom de la société (pas de secteurs d'activité, de slogan, etc.).
     - Ne rien renvoyer si aucun nom de titulaire trouvé.
""",
    },
    "adresse_postale_titulaire": ADRESSE_POSTALE_TITULAIRE,
    "domiciliation": {
        "consigne": """
     Définition : Domiciliation du compte bancaire (si effectuée).
     Indices : 
     - Rechercher la domiciliation du compte bancaire dans la section du RIB.
     - Renvoyer la domiciliation bancaire complète telle qu'écrite sur le RIB.
     - Ne rien renvoyer si aucune domiciliation trouvée.
""",
    },
    "banque": {
        "consigne": """
     Définition : Nom de la banque.
     Indices : 
     - Rechercher le nom de la banque d'où provient le RIB.
     - Ne rien renvoyer si aucune banque trouvée.
""",
    },
}
