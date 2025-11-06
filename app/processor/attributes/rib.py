"""
Définitions des attributs à extraire pour les documents de type "rib".
"""

RIB_ATTRIBUTES = {
    "iban": {
        "consigne": """IBAN
     Définition : Identifiant international de compte bancaire (IBAN), généralement composé de 27 caractères commençant par "FR" pour la France.
     Indices : 
     - Repérer les identifiants sous la forme "FR76..." ou similaires, souvent précédés de la mention "IBAN" ou "N° IBAN".
     - Chercher dans la section du RIB ou dans un tableau récapitulatif des coordonnées bancaires.
     - Ne rien renvoyer si aucun IBAN n'est clairement identifié.
""",
        "search": "",
        "output_field": "iban"
    },

    "bic": {
        "consigne": """BIC
     Définition : Code d'identification bancaire (BIC), généralement composé de 8 ou 11 caractères alphanumériques.
     Indices : 
     - Repérer les codes sous la forme "BIC" ou "Code BIC", souvent présents dans un RIB.
     - Chercher dans la section du RIB ou dans un tableau récapitulatif des coordonnées bancaires.
     - Ne rien renvoyer si aucun BIC n'est clairement identifié.
""",
        "search": "",
        "output_field": "bic"
    },

    "titulaire_compte": {
        "consigne": """TITULAIRE_COMPTE
     Définition : Nom du titulaire du compte bancaire.
     Indices : 
     - Rechercher le nom du titulaire du compte bancaire dans la section du RIB.
     - Ne rien renvoyer si aucun nom de titulaire trouvé.
""",
        "search": "",
        "output_field": "titulaire_compte"
    },

    "adresse_postale_titulaire": {
        "consigne": """ADRESSE_POSTALE_TITULAIRE  
     Définition : Adresse postale complète de la société titulaire principale du marché.  
     Indices : 
     - Rechercher l'adresse dans la section du titulaire principal.
     - Inclure le numéro, la rue, le code postal, la ville et le pays si mentionné.
     - Ne rien renvoyer si aucune adresse trouvée.
     Format : adresse complète en bon français.
""",
        "search": "",
        "output_field": "adresse_postale_titulaire"
    },

    "domiciliation": {
        "consigne": """DOMICILIATION
     Définition : Domiciliation du compte bancaire.
     Indices : 
     - Rechercher la domiciliation du compte bancaire dans la section du RIB.
     - Ne rien renvoyer si aucune domiciliation trouvée.
""",
        "search": "",
        "output_field": "domiciliation"
    },
}

