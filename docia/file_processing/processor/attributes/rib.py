"""
Définitions des attributs à extraire pour les documents de type "rib".
"""

RIB_ATTRIBUTES = {
    "iban": {
        "consigne": """IBAN
     Définition : Identifiant international de compte bancaire (IBAN)
     Indices : 
     - Généralement composé de 27 caractères (pour un RIB Français), commençant souvent par "FR" pour un IBAN en France (souvent "FR76 ...", "FR09 ..." ou autres)
     - Souvent 6 groupes de 4 caractères, puis 3 caractères.
     - Si aucun IBAN trouvé, renvoyer ''
     Format : l'IBAN d'entre 21 et 27 caractères (27 si commence par FR) caractères avec espaces tous les 4 caractères (6 groupes de 4 et un groupe de 3)
""",
        "search": "",
        "output_field": "iban",
    },
    "bic": {
        "consigne": """BIC
     Définition : Code d'identification bancaire (BIC), généralement composé de 8 ou 11 caractères alphanumériques.
     Indices : 
     - Repérer les codes sous la forme "BIC" ou "Code BIC", souvent présents dans un RIB.
     - Chercher dans la section du RIB ou dans un tableau récapitulatif des coordonnées bancaires.
     - Ne rien renvoyer si aucun BIC n'est clairement identifié.
     Format : le BIC de 8 ou 11 caractères avec espaces tous les 4 caractères
""",
        "search": "",
        "output_field": "bic",
    },
    "titulaire_compte": {
        "consigne": """TITULAIRE_COMPTE
     Définition : Nom du titulaire du compte bancaire (personne physique ou morale).
     Indices : 
     - Rechercher le nom du titulaire (personne physique ou morale)du compte bancaire dans la section du RIB.
     - S'il s'agit d'une personne morale, renvoyer le nom de la société ou de l'établissement.
        * Pas besoin de renvoyer d'informations sur la direction ou du service interne de la société titulaire.
        * Pas besoin de renvoyer d'informations autres que le nom de la société (pas de secteurs d'activité, de slogan, etc.).
     - Ne rien renvoyer si aucun nom de titulaire trouvé.
""",
        "search": "",
        "output_field": "titulaire_compte",
    },
    "adresse_postale_titulaire": {
        "consigne": """ADRESSE_POSTALE_TITULAIRE  
     Définition : Adresse postale  de la société titulaire principale du marché (json).
     Indices : 
     - Rechercher l'adresse postale indiquée sur ce RIB. 
     - Attention, on cherche l'adresse du titulaire du compte, pas celle de la banque.
     - Extraire tous les éléments disponibles :
        * le numéro de voie
        * le nom de la voie
        * le complément d'adresse éventuel (bâtiment, étage, BP, etc.)
        * le code postal
        * la ville
        * le pays (indiquer 'France' si le pays n'est pas mentionné mais implicite)
     - Si aucune adresse trouvée pour le titulaire du compte, renvoyer ''
     Format : un json sous format suivant : {'numero_voie': 'le numéro de voie', 'nom_voie': 'le nom de la voie', 'complement_adresse': 'le complément d'adresse éventuel', 'code_postal': 'le code postal', 'ville': 'la ville','pays': 'le pays'}
""",
        "search": "",
        "output_field": "adresse_postale_titulaire",
        "schema": {
            "type": "object",
            "properties": {
                "numero_voie": {"type": "string"},
                "nom_voie": {"type": "string"},
                "complement_adresse": {"type": "string"},
                "code_postal": {"type": "string"},
                "ville": {"type": "string"},
                "pays": {"type": "string"},
            },
            "required": ["numero_voie", "nom_voie", "complement_adresse", "code_postal", "ville", "pays"],
        },
    },
    "domiciliation": {
        "consigne": """DOMICILIATION
     Définition : Domiciliation du compte bancaire (si effectuée).
     Indices : 
     - Rechercher la domiciliation du compte bancaire dans la section du RIB.
     - Renvoyer la domiciliation bancaire complète telle qu'écrite sur le RIB.
     - Ne rien renvoyer si aucune domiciliation trouvée.
""",
        "search": "",
        "output_field": "domiciliation",
    },
    "banque": {
        "consigne": """BANQUE
     Définition : Nom de la banque.
     Indices : 
     - Rechercher le nom de la banque d'où provient le RIB.
     - Ne rien renvoyer si aucune banque trouvée.
""",
        "search": "",
        "output_field": "banque",
    },
}
