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
     Définition : Adresse postale complète de la société titulaire principale du marché.  
     Indices : 
     - Rechercher l'adresse dans la section du titulaire principal.
     - Inclure le numéro, la rue, le code postal, la ville et le pays si mentionné.
     - Ne rien renvoyer si aucune adresse trouvée.
     Format : adresse complète en bon français.
""",
        "search": "",
        "output_field": "adresse_postale_titulaire",
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
     Définition : Adresse postale complète de la société sous-traitante.  
     Indices : 
     - Rechercher l'adresse dans la section du sous-traitant.
     - Inclure le numéro, la rue, le code postal, la ville et le pays si mentionné.
     - Ne rien renvoyer si aucune adresse trouvée.
     Format : adresse complète en bon français.
""",
        "search": "",
        "output_field": "adresse_postale_sous_traitant",
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
}
