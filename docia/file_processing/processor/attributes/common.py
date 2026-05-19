"""
Prompts et schémas partagés entre types de documents (hors avenant).
"""

SCHEMA_ADRESSE_POSTALE = {
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
}

SCHEMA_DUREE = {
    "type": "object",
    "properties": {
        "duree_initiale": {"type": ["integer", "null"]},
        "duree_reconduction": {"type": ["integer", "null"]},
        "nb_reconductions": {"type": ["integer", "null"]},
        "delai_tranche_optionnelle": {"type": ["integer", "null"]},
    },
    "required": ["duree_initiale", "duree_reconduction", "nb_reconductions", "delai_tranche_optionnelle"],
}

SCHEMA_RIB = {
    "type": "object",
    "properties": {
        "banque": {"type": ["string", "null"]},
        "iban": {"type": ["string", "null"]},
        "code_banque": {"type": ["string", "null"]},
        "code_guichet": {"type": ["string", "null"]},
        "numero_compte": {"type": ["string", "null"]},
        "cle_rib": {"type": ["string", "null"]},
    },
}

SCHEMA_CONSERVE_AVANCE = {
    "type": "string",
    "enum": ["conserve", "renonce", ""],
}

SCHEMA_LISTE_ENTREPRISE_SIRET = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"nom": {"type": "string"}, "siret": {"type": "string"}},
        "required": ["nom", "siret"],
    },
}

ACTIVITE_PRINCIPALE = {
    "consigne": """
     Définition : Activité principale exercée (APE) de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher l'activité principale de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune activité principale trouvée.
""",
}

ADRESSE_POSTALE_INSEE = {
    "consigne": """
     Définition : Adresse postale de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher l'adresse postale de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune adresse postale trouvée.
""",
}

DENOMINATION = {
    "consigne": """
     Définition : Dénomination de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher la dénomination de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune dénomination trouvée.
""",
}

DESCRIPTION_PRESTATIONS = {
    "consigne": """
   Définition : Description des prestations de la commande ou du marché, structurée et compréhensible.
   Indices : 
   - Un texte décrivant le contenu de la prestation, des services attendus ou réalisés, et du matériel utilisé ou acheté.
   - Des précisions si disponibles sur la date ou la période, le lieu de la prestation, les quantités sont bienvenues.
   - Attention à ne pas renvoyer de données personnelles (nom, prénom, adresse postales ou coordonnées).
   - Attention à ne pas renvoyer de détails de prix.
   Format : en bon Français, reformulé si besoin.
   """,
}

SIRET = {
    "consigne": """
   Définition : Numéro SIRET de la société principale, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", ou "numéro d'immatriculation"
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
}

ADMINISTRATION_BENEFICIAIRE = {
    "consigne": """
     Définition : Structure administrative ou publique qui bénéficie de la commande, ou qui achète la prestation.
     Indices :
     - Rechercher les mentions d'achateurs, de pouvoir adjudicateur, ou d'autorité contractante. Le résultat est souvent une direction ou un service au sein d'une administration.
     - Si aucune information n'est trouvée sur l'administration bénéficiaire : renvoyer ''.
     - Si possible, inclure le nom de l'administration jusqu'à deux sous-niveaux organisationnels.
        * Exemple de bon résultat : Ministère de la culture (MDC) - Secrétariat général (SG) - Direction des musées de France (DMF)
        * Exemple de résultat trop général : Ministère de la culture (MC)
        * Exemple de résultat insuffisant : Direction des musées de France (DMF)
        * Exemple de résultat trop détaillé : Ministère de la culture (MC) - Secrétariat général (SG) - Direction des musées de France (DMF) - Service des musées d'artisanat (SMA)
     - S'il est seulement précisé les rôles ou les postes de persones, déduire la direction / le service / l'administration bénéficiaire.
        * Exemple : le préfet de la région Île-de-France -> Préfecture de la région Île-de-France
     Format : les différents niveaux de l'administration bénéficiaire en minuscule correctement écrit (et leurs acronymes entre parenthèses si disponibles), séparés par des tirets, . 
""",
}

SOCIETE_PRINCIPALE = {
    "consigne": """
     Définition : Société principale contractante (titulaire). Si un groupement est mentionné, extraire la société mandataire ou représentante.  
     Indices : 
     - Rechercher les mentions de société, entreprise, titulaire, mandataire, contractant ou tiers.
     - En général, l'autre nom de personne morale que l'administration acheteuse.
     - Les noms de domaine des adresses mails peuvent donner des indices sur la bonne orthographe.
     Format : renvoyer le nom de la société.
""",
}

OBJET_MARCHE = {
    "consigne": """
   Définition : l'objet du marché, c'est-à-dire ce qui a été acheté, ou le service fourni.
   Indices :
   - Chercher après les mentions "Objet :", ou autre mention similaire.
   - Généralement en début de document ou après les coordonnées.
   - Dans tous les cas, l'objet du marché doit avoir du sens pour une personne extérieure, et permettre de comprendre l'achat.
   - Ne rien renvoyer si aucun objet trouvé
   Format : 
   - En bon Français
   - Attention, ne pas inclure le type de document dans l'objet : "Devis pour ..." enlever "Devis pour" / "Avenant pour ..." enlever "Avenant pour".
   - Si l'objet de la commande est incompréhensible, proposer un objet simple qui reflète le contenu de la commande.
""",
}

MONTANT_HT = {
    "consigne": """
     Définition : Montant du marché hors taxes (également hors TVA).  
     Indices : 
     - Rechercher les mentions "hors taxes", "HT", "sans TVA", "hors TVA" ou équivalent. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Cas particuliers :
        * Pour un marché en plusieurs lots (cf champ lot_concerne), ne renvoyer que le montant (maximum) du lot concerné.
        * Pour un marché en plusieurs tranches, renvoyer la somme des montants de toutes les tranches.
     - Ne rien envoyer si aucun montant HT trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
}

MONTANT_TTC = {
    "consigne": """
     Définition : Montant du marché toutes taxes comprises (avec TVA incluse).  
     Indices : 
     - Rechercher les expressions "TTC", "TVA incluse", "TVA comprise".
     - Ignorer les montants HT (hors taxes) et le montant de TVA seule
     - Le montant TTC peut être le même que le montant HT, s'il n'y a pas de TVA.
     - Cas particuliers :
        * Pour un marché en plusieurs lots (cf champ lot_concerne), ne renvoyer que le montant du lot concerné.
        * Pour un marché en plusieurs tranches, renvoyer la somme des montants de toutes les tranches.
     - Ne rien envoyer si aucun montant TTC trouvé, ou si le montant a plus de chance d'être en HT que en TTC.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
}

MONTANT_TVA = {
    "consigne": """
        Définition : Montant de la TVA.
        Indices :
        - Rechercher la mention de TVA ou de "taux de TVA". Le montant est souvent sous la forme d'un pourcentage.
        - Convertir le pourcentage en chiffre décimal entre 0 et 1.
        - Ne rien renvoyer si aucun montant de TVA trouvé. Ne pas calculer le taux entre deux montants HT et TTC.
        Format : exprimé en décimales (ex: 0.20, 0.055), pas en pourcentage.
        """,
}

OBJET = {
    "consigne": """
   Définition : l'objet de la commande ou du marché, c'est-à-dire ce qui a été acheté, ou le service fourni.
   Indices :
   - Chercher après les mentions "Objet :", ou autre mention similaire.
   - Généralement en début de document ou après les coordonnées.
   - Dans tous les cas, l'objet de la commande doit avoir du sens pour une personne extérieure, et permettre de comprendre l'achat.
   - Ne rien renvoyer si aucun objet trouvé
   Format : 
   - En bon Français
   - Attention, ne pas inclure le type de document dans l'objet : "Devis pour ..." enlever "Devis pour" / "Avenant pour ..." enlever "Avenant pour".
   - Si l'objet de la commande est incompréhensible, proposer un objet simple qui reflète le contenu de la commande.
""",
}

SIREN = {
    "consigne": """
   Définition : numéro de SIREN du prestataire / du titulaire principal, composé de 9 chiffres
   Indices :
   - Après la mention SIREN au début ou à la fin du document.
   - A partir d'un numéro de SIRET : les 9 premiers chiffres d'un SIRET de 14 chiffres.
   - A partir d'un numéro RCS : les 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
   - A partir d'un numéro de TVA : les 9 derniers chiffres du numéro de TVA (après l'identifiant du pays et du département ex : FR12)
   - Ne rien renvoyer si aucun SIREN trouvé
   Format : un numéro composé de 9 chiffres, sans espaces ni caractères spéciaux
   - Dans un extrait Kbis : rechercher le numéro SIREN de la personne morale.
""",
}

CONSERVE_AVANCE = {
    "consigne": """
        Définition : Information sur la volonté du titulaire de conserver ou de renoncer au bénéfice de l'avance.
        Indices :
        Le texte présente souvent une phrase de type "Je renonce au bénéfice de l'avance" suivie de deux options : [ ] Non et [ ] Oui.
        1. Identifie quelle case est cochée (représentée par [X], [x], X, x, ☒ ou autre équivalent) et quelle case ne l'est pas (représentée par [ ], un espace ou autre équivalent).
        - La coche appartient à l’option (NON ou OUI) la plus proche spatialement.
        - Si la coche est située entre "NON" et "OUI", elle est associée à l’option située immédiatement à droite.
        2. Analyse le sens : 
        - Si "Renonce" est associé à "NON" (coché) -> L'utilisateur VEUT l'avance -> Renvoyer "conserve"
        - Si "Renonce" est associé à "OUI" (coché) -> L'utilisateur REFUSE l'avance -> Renvoyer "renonce"
        - Si la phrase est "Je souhaite BENEFICIER de l'avance" : Oui = Conserve -> Renvoyer "conserve", Non = Renonce -> Renvoyer "renonce"
        - Uniquement si le paragraphe est totalement absent ou si aucune mention ([X], [x], X ou x n'est présente) -> Renvoyer null
""",
    "schema": SCHEMA_CONSERVE_AVANCE,
}

CONSERVE_AVANCE_SOUS_TRAITANT = {
    "consigne": """
        Définition : Information sur la volonté du sous-traitant de conserver ou de renoncer au bénéfice de l'avance.
        Indices :
        Le texte présente souvent une phrase de type "Je renonce au bénéfice de l'avance" suivie de deux options : [ ] Non et [ ] Oui.
        1. Identifie quelle case est cochée (représentée par [X], [x], X, x, ☒ ou autre équivalent) et quelle case ne l'est pas (représentée par [ ], un espace ou autre équivalent).
        - La coche appartient à l’option (NON ou OUI) la plus proche spatialement.
        - Si la coche est située entre "NON" et "OUI", elle est associée à l’option située immédiatement à droite.
        2. Analyse le sens : 
        - Si "Renonce" est associé à "NON" (coché) -> L'utilisateur VEUT l'avance -> Renvoyer "conserve"
        - Si "Renonce" est associé à "OUI" (coché) -> L'utilisateur REFUSE l'avance -> Renvoyer "renonce"
        - Si la phrase est "Je souhaite BENEFICIER de l'avance" : Oui = Conserve -> Renvoyer "conserve", Non = Renonce -> Renvoyer "renonce"
        - Uniquement si le paragraphe est totalement absent ou si aucune mention ([X], [x], X ou x n'est présente) -> Renvoyer null
""",
    "schema": SCHEMA_CONSERVE_AVANCE,
}

DATE_SIGNATURE = {
    "consigne": """
      Définition : Date de signature du document par une des parties.  
      Indices : 
      - Repérer les expressions comme "Signé le", "Fait à ...", ou des dates en bas du document associées à une signature.
      - Ignorer les dates d'émission ou de création du document, en général en haut du document
      - Ne rien renvoyer si aucune date de signature trouvée
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
}

DATE_SIGNATURE_DERNIERE = {
    "consigne": """
      Définition : Date de dernière signature du document par une des parties.  
      Indices : 
      - Repérer les expressions comme "Signé le", "Fait à ...", ou des dates en bas du document associées à une signature.
      - Ignorer les dates d'émission ou de création du document, en général en haut du document
      - Ne rien renvoyer si aucune date de signature trouvée
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
}

ADRESSE_POSTALE_TITULAIRE = {
    "consigne": """
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
    "schema": SCHEMA_ADRESSE_POSTALE,
}
