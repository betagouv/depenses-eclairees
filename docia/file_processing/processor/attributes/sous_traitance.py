"""
Définitions des attributs à extraire pour les documents de type "sous_traitance".
"""

SOUS_TRAITANCE_ATTRIBUTES = {
    "administration_beneficiaire": {
        "consigne": """ADMINISTRATION_BENEFICIAIRE 
     Définition : Structure administrative ou publique qui bénéficie de la commande, ou qui achète la prestation.
     Indices :
     - Rechercher les mentions d'achateurs, de pouvoir adjudicateur, ou d'autorité contractante.
     - Le résultat est souvent une direction, un service, ou une administration.
     - S'il est seulement précisé les rôles ou les postes de persones (ex : le préfet de la région Île-de-France), déduire la direction / le service / l'administration bénéficiaire (ex : la préfecture de la région Île-de-France).
     Format : le nom de l'administration bénéficiaire en toutes lettres (pas d'acronymes si possible). 
""",
        "search": "",
        "output_field": "administration_bénéficiaire",
    },
    "objet_marche": {
        "consigne": """OBJET_MARCHE
     Définition : Formulation synthétique de l'objet du marché.
     Indices : 
     - L'objet du marché peut être dans le titre directement, ou plus généralement dans une section dédiée.
     - Identifier les formules comme "Objet du marché", "Le marché a pour objet", ou toute expression indiquant l'intitulé de la mission.  
""",
        "search": "Section du document qui décrit l'objet du marché ou le contexte général de la consultation.",
        "output_field": "objet_marche",
    },
    "societe_principale": {
        "consigne": """SOCIETE_PRINCIPALE  
     Définition : Société principale contractante avec l'administration publique ou ses représentants. Si un groupement est mentionné, extraire la société mandataire ou représentante.  
     Indices : 
     - Rechercher les mentions de société, entreprise, titulaire, mandataire, contractant.
     - En général, l'autre nom de personne morale que l'administration acheteuse.
     - Le nom de la société est souvent cohérent avec le nom de domaine du site interne.
     Format : renvoyer le nom de la société telle qu'écrit dans le document.
""",
        "search": "",
        "output_field": "societe_principale",
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
    "siret_titulaire": {
        "consigne": """SIRET_TITULAIRE  
   Définition : Numéro SIRET du titulaire principal du marché, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", "numéro d'immatriculation" ou "SIRET du titulaire"
   - Rechercher dans la section du titulaire principal du marché
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
        "search": "",
        "output_field": "siret_titulaire",
    },
    "societe_sous_traitant": {
        "consigne": """SOCIETE_SOUS_TRAITANT  
     Définition : Société sous-traitante qui réalise une partie des prestations du marché.  
     Indices : 
     - Rechercher les mentions de société, entreprise, sous-traitant dans la section dédiée à la sous-traitance.
     - Le nom de la société sous-traitante est généralement distinct de la société principale.
     Format : renvoyer le nom de la société sous-traitante telle qu'écrit dans le document.
""",
        "search": "",
        "output_field": "societe_sous_traitant",
    },
    "adresse_postale_sous_traitant": {
        "consigne": """ADRESSE_POSTALE_SOUS_TRAITANT  
     Définition : Adresse postale  de la société sous-traitant (json).
     Indices : 
     - Rechercher l'adresse postale indiquée sur la sous-traitance. 
     - Extraire tous les éléments disponibles :
        * le numéro de voie
        * le nom de la voie
        * le complément d'adresse éventuel (bâtiment, étage, BP, etc.)
        * le code postal
        * la ville
        * le pays (indiquer 'France' si le pays n'est pas mentionné mais implicite)
     - Si aucune adresse trouvée pour le sous-traitant, renvoyer {}
     Format : un json sous format suivant : {'numero_voie': 'le numéro de voie', 'nom_voie': 'le nom de la voie', 'complement_adresse': 'le complément d'adresse éventuel', 'code_postal': 'le code postal', 'ville': 'la ville','pays': 'le pays'}
""",
        "search": "",
        "output_field": "adresse_postale_sous_traitant",
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
    "siret_sous_traitant": {
        "consigne": """SIRET_SOUS_TRAITANT  
   Définition : Numéro SIRET du sous-traitant, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", "numéro d'immatriculation" ou "SIRET du sous-traitant"
   - Rechercher dans la section du sous-traitant
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
        "search": "",
        "output_field": "siret_sous_traitant",
    },
    "montant_sous_traitance_ht": {
        "consigne": """MONTANT_SOUS_TRAITANCE_HT  
     Définition : Montant de la sous-traitance hors taxes (également hors TVA).  
     Indices : 
     - Rechercher les mentions "hors taxes", "HT", "sans TVA" ou équivalent dans la section sous-traitance. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Ne rien envoyer si aucun montant trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
     """,
        "search": "",
        "output_field": "montant_sous_traitance_ht",
    },
    "montant_sous_traitance_ttc": {
        "consigne": """MONTANT_SOUS_TRAITANCE_TTC  
     Définition : Montant de la sous-traitance toutes taxes comprises (ou avec TVA incluse).  
     Indices : 
     - Rechercher les expressions "TTC", "TVA incluse", "TVA comprise" dans la section sous-traitance. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Ignorer les montants HT (hors taxes) et le montant de TVA seule
     - Ne rien envoyer si aucun montant trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
        "search": "",
        "output_field": "montant_sous_traitance_ttc",
    },
    "description_prestations": {
        "consigne": """DESCRIPTION_PRESTATIONS
   Définition : Description des prestations de la commande ou du marché, structurée et compréhensible.
   Indices : 
   - Un texte décrivant le contenu de la prestation, des services attendus ou réalisés, et du matériel utilisé ou acheté.
   - Des précisions si disponibles sur la date ou la période, le lieu de la prestation, les quantités sont bienvenues.
   - Attention à ne pas renvoyer de données personnelles (nom, prénom, adresse postales ou coordonnées).
   - Attention à ne pas renvoyer de détails de prix.
   Format : en bon Français, reformulé si besoin.
   """,
        "search": "",
        "output_field": "description_prestations",
    },
    "date_signature": {
        "consigne": """DATE_SIGNATURE
      Définition : Date de signature du document par une des parties.  
      Indices : 
      - Repérer les expressions comme "Signé le", "Fait à ...", ou des dates en bas du document associées à une signature.
      - Ignorer les dates d'émission ou de création du document, en général en haut du document
      - Ne rien renvoyer si aucune date de signature trouvée
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
        "search": "",
        "output_field": "date_signature",
    },
    "montant_tva": {
        "consigne": """MONTANT_TVA
     Définition : Montant de la TVA.
     Indices : 
     - Rechercher le taux de la TVA dans la section du sous traitant.
     - Ne rien renvoyer si aucune indication trouvée.
     Format : "0.20" ou "0.055" et non "20%" ou "5.5%"
     Ne rien renvoyer si aucune indication trouvée.
""",
        "search": "",
        "output_field": "montant_tva",
    },
    "paiement_direct": {
        "consigne": """PAIEMENT_DIRECT
     Définition : Indique si le sous traitant est eligible au paiement direct.
     Indices : 
     - Rechercher les expressions "eligible au paiement direct", "eligible au paiement indirect", "eligible au paiement en direct", "eligible au paiement en indirect", "eligible au paiement directement", "eligible au paiement indirectement".
     - Ne rien renvoyer si aucune indication trouvée.
     Format : "oui" ou "non".
""",
        "search": "",
        "output_field": "paiement_direct",
        "schema": {
            "type": "string",
            "enum": ["oui", "non", ""],
        },
    },
    "rib_sous_traitant": {
        "consigne": """RIB_SOUS_TRAITANT
     Définition : Informations bancaires (IBAN en priorité) du compte à créditer indiqué dans la sous-traitance.
     Indices : 
     - Rechercher dans les informations bancaires, en priorité près des mentions "RIB" ou "IBAN".
     - 1er cas (prioritaire) : l'IBAN est fourni (27 caractères commençant par "FR76"). Renvoyer :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'iban' : IBAN du compte à créditer (souvent 6 groupes de 4 caractères, puis 3 caractères)
     - 2ème cas (uniquement s'il n'y a pas d'IBAN) : l'IBAN n'est pas fourni, mais les autres informations bancaires sont fournies. Renvoyer :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'code_banque' : code de la banque à 5 chiffres (espaces non compris)
        * 'code_guichet' : code du guichet à 5 chiffres (espaces non compris)
        * 'numero_compte' : numéro de compte français à 11 chiffres (espaces non compris)
        * 'cle_rib' : clé du RIB à 2 chiffres (espaces non compris)
     - Si aucune information bancaire trouvée pour le sous-traitant (ni IBAN, ni informations seules), renvoyer {}.
     Format : 
     - 1er cas (prioritaire) : un json sous format suivant {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}
     - 2ème cas (secondaire - uniquement s'il n'y a pas d'IBAN) : un json sous format suivant {"banque": "nom de la banque", "code_banque": "code de la banque à 5 chiffres", "code_guichet": "code du guichet à 5 chiffres", "numero_compte": "numéro de compte à 11 chiffres", "cle_rib": "clé du RIB à 2 chiffres"}
""",
        "search": "",
        "output_field": "rib_sous_traitant",
        "schema": {
            "type": "object",
            "oneOf": [
                {
                    "type": "object",
                    "properties": {"banque": {"type": "string"}, "iban": {"type": "string"}},
                    "required": ["banque", "iban"],
                },
                {
                    "type": "object",
                    "properties": {
                        "banque": {"type": "string"},
                        "code_banque": {"type": "string"},
                        "code_guichet": {"type": "string"},
                        "numero_compte": {"type": "string"},
                        "cle_rib": {"type": "string"},
                    },
                    "required": ["banque", "code_banque", "code_guichet", "numero_compte", "cle_rib"],
                },
                {},
            ],
        },
    },
    "conserve_avance": {
        "consigne": """CONSERVE_AVANCE
     Définition : Indique si le sous traitant conserve l'avance.
     Indices : 
     - Rechercher les expressions "conserve l'avance", "conserve l'avancement", "conserve l'avancement", "conserve l'avancement", "conserve l'avancement", "conserve l'avancement".
     - Ne rien renvoyer si aucune indication trouvée.
     Format : "conserve" ou "renonce".
""",
        "search": "",
        "output_field": "conserve_avance",
        "schema": {
            "type": "string",
            "enum": ["conserve", "renonce", ""],
        },
    },
    "duree_sous_traitance": {
        "consigne": """DUREE_SOUS_TRAITANCE
        Définition : Durée de la sous-traitance totale exprimée en mois et extension possible.
        Indices :
        - Chercher dans le paragraphe indiquant la durée de la sous-traitance ou le délai d'exécution des prestations.
        - Durée initiale : la durée de la sous-traitance ferme (sans reconduction ou tranches optionnelles), en nombre de mois.
            * En l'absence de précisions sur la durée ferme, renvoyer duree_initiale: null
            * Exemple : une durée de 1 an, renvoyer 12. une durée de 2 semaines, renvoyer 1.
            * Pour une durée entre des dates clés, par exemple "jusqu'à la réunion de conclusion 6 mois après le lancement" : renvoyer 6 mois.
                -> Attention : si ces dates clés sont insuffisamment documentées, renvoyer duree_initiale: null
        - Extension de durée possible : extension maximale en nombre de mois.
            * En l'absence d'informations claires, renvoyer duree_reconduction: null
            * Si des reconductions sont précisées (ne pas confondre avec des tranches optionnelles qui sont gérées ci-dessous) :
                1. duree_reconduction : Trouver la durée d'une reconduction (en nombre de mois). Si l'information n'est pas précisée ou qu'il n'y a pas de reconduction, renvoyer null.
                2. nb_reconductions : Trouver le nombre de reconductions possibles (éventuellement 0). Si l'information n'est pas précisée ou qu'il n'y a pas de reconduction, renvoyer null.
            * Si des tranches optionnelles sont précisées : renvoyer la durée de l'ensemble des tranches optionnelles.
                1. delai_tranche_optionnelle : Trouver la durée de l'ensemble des tranches optionnelles. Si l'information n'est pas précisée ou qu'il n'y a pas de tranches optionnelles, renvoyer null.
                    Exemple : 2 tranches optionnelles de 8 mois, renvoyer 8 + 8 = 16.
        Format : un json sous format suivant {"duree_initiale": "nombre entier de mois", "duree_reconduction": "nombre entier de mois", "nb_reconductions": "nombre entier de reconductions possibles", "delai_tranche_optionnelle": "nombre entier de mois"}
    """,
        "search": "Section du document qui décrit la durée du marché ou le délai d'exécution des prestations.",
        "output_field": "duree_sous_traitance",
        "schema": {
            "type": "object",
            "properties": {
                "duree_initiale": {"type": ["integer", "null"]},
                "duree_reconduction": {"type": ["integer", "null"]},
                "nb_reconductions": {"type": ["integer", "null"]},
                "delai_tranche_optionnelle": {"type": ["integer", "null"]},
            },
            "required": ["duree_initiale", "duree_reconduction", "nb_reconductions", "delai_tranche_optionnelle"],
        },
    },
}
