"""
Définitions des attributs à extraire pour les documents de type "avenant".
"""

AVENANT_ATTRIBUTES = {
    "objet": {
        "consigne": """OBJET
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
        "search": "",
        "output_field": "objet"
    },

    "type_document": {
        "consigne": """TYPE_DOCUMENT
   Définition : catégorie juridique ou administrative du document.
   Indices :
   - Le type de document est souvent mentionné au début du document dans le titre ou le sous-titre.
   - Exemples de types de documents : devis, acte d'engagement, avenant, bon de commande, cachier des charges, ...
   - Ne rien renvoyer si aucun type de document trouvé
   Format : en minuscule, sans accent, sans espace (ex: "devis", "acte_engagement", "bon_de_commande")
""",
        "search": "",
        "output_field": "type_document"
    },

    "montant_ht": {
        "consigne": """MONTANT_HT  
     Définition : Montant du marché hors taxes (également hors TVA).  
     Indices : 
     - Rechercher les mentions "hors taxes", "HT", "sans TVA" ou équivalent. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Ne rien envoyer si aucun montant trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
     """,
        "search": "",
        "output_field": "montant_ht"
    },

    "montant_ttc": {
        "consigne": """MONTANT_TTC  
     Définition : Montant du marché toutes taxes comprises (ou avec TVA incluse).  
     Indices : 
     - Rechercher les expressions "TTC", "TVA incluse", "TVA comprise". 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Ignorer les montants HT (hors taxes) et le montant de TVA seule
     - Ne rien envoyer si aucun montant trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
        "search": "",
        "output_field": "montant_ttc"
    },

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
        "output_field": "administration_bénéficiaire"
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
        "output_field": "description_prestations"
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
        "output_field": "societe_principale"
    },

    "siret": {
        "consigne": """SIRET  
   Définition : Numéro SIRET de la société principale, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", ou "numéro d'immatriculation"
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
        "search": "",
        "output_field": "siret"
    },

    "siren": {
        "consigne": """SIREN
   Définition : numéro de SIREN du prestataire / du titulaire principal, composé de 9 chiffres
   Indices :
   - Après la mention SIREN au début ou à la fin du document.
   - A partir d'un numéro de SIRET : les 9 premiers chiffres d'un SIRET de 14 chiffres.
   - A partir d'un numéro RCS : les 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
   - A partir d'un numéro de TVA : les 9 derniers chiffres du numéro de TVA (après l'identifiant du pays et du département ex : FR12)
   - Ne rien renvoyer si aucun SIREN trouvé
   Format : un numéro composé de 9 chiffres, sans espaces ni caractères spéciaux
""",
        "search": "",
        "output_field": "siren"
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
        "output_field": "date_signature"
    },
}

