"""
Définitions des attributs à extraire pour les documents de type "acte_engagement".
"""

ACTE_ENGAGEMENT_ATTRIBUTES = {
    "objet": {
        "consigne": """OBJET
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
        "search": "",
        "output_field": "objet"
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

    "siret_mandataire": {
        "consigne": """SIRET_MANDATAIRE  
   Définition : Numéro SIRET de la société principale, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", ou "numéro d'immatriculation"
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
        "search": "",
        "output_field": "siret_mandataire"
    },

    "siren_mandataire": {
        "consigne": """SIREN_MANDATAIRE
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
        "output_field": "siren_mandataire"
    },

    "rib_mandataire": {
        "consigne": """RIB_MANDATAIRE
     Définition : Informations bancaires du compte à créditer indiqué dans l'acte d'engagement.
     Indices : 
     - Rechercher les informations bancaires du mandataire dans la section des comptes à créditer.
     - Informations à trouver : 
        * 'banque' : Nom de la banque
        * 'code_banque' : code de la banque à 5 chiffres
        * 'code_guichet' : code du guichet à 5 chiffres
        * 'numero_compte' : numéro de compte français à 11 chiffres
        * 'cle_rib' : clé du RIB à 2 chiffres
    - Si l'IBAN est indiqué, on peut déduire les autres informations de la manière suivante :
        * IBAN = 'FR76' + code_banque + code_guichet + numero_compte + cle_rib
        * 'FR76' peut être remplacé par 4 autres caractères pour un code d'un autre pays.
    - Si l'IBAN n'est pas indiqué, certaines informations peuvent être tout de même présentes seules.
    - Ne rien renvoyer si aucune information bancaire trouvée pour le mandataire (ni IBAN, ni informations seules).
     Format : un dictionnaire json sous format suivant {'banque': 'nom de la banque', 'code_banque': 'code de la banque à 5 chiffres', 'code_guichet': 'code du guichet à 5 chiffres', 'numero_compte': 'numéro de compte français à 11 chiffres', 'cle_rib': 'clé du RIB à 2 chiffres'}
""",
        "search": "",
        "output_field": "rib_mandataire"
    },

#     "avance":{
#         "consigne": """AVANCE
#      Définition : Information sur la volonté du titulaire de recevoir ou non une avance.
#      Indices :
#      - Dans un paragraphe dédié au renoncement de l'avance, souvent sous la forme d'une case à cocher à gauche de la mention "Non" ou "Oui".
#      - Attention l'extraction du texte peut être ambiguë, notamment pour les cases à cocher :
#         * si une des cases est devenu 0 ou O, elle n'était probalement pas cochée : "Ef NON O oul", c'était probablement que "Non" était cochée.
#         * si une des cases est devenu x ou X, elle était probablement cochée.
#         * si la coche d'une case n'est pas clairement visible, renvoyer "Information insuffisante".
#      - Ne rien renvoyer sur l'avance si aucune information sur l'avance trouvée.
#      Format : "✓ Conserve le bénéfice de l'avance" ou "✗ Renonce au bénéfice de l'avance" ou "Information insuffisante
# """,
#         "search": "",
#         "output_field": "avance"
#     },

    "citation_avance":{
        "consigne": """CITATION_AVANCE
     Définition : La question (souvent "Je renonce au bénéfice de l'avance :")et les réponses extraites du texte du document concernant l'avance.
     Format : La citation du texte du document telle quelle, sans aucune modification.
""",
        "search": "",
        "output_field": "citation_avance"
    },


    "cotraitants":{
        "consigne": """COTRAITANTS
     Définition : Liste des entreprises cotraitantes autres que le mandataire (entreprise principale).
     Indices : 
     - Rechercher dans le paragraphe de description du groupement, s'il y a des entreprises en plus du mandataire avec le statut de cotraintant (et non pas sous-traitantes).
     - Attention, les cotraitants peuvent aussi être mentionnés dans les prestations, ou dans les comptes à créditer. Si c'est le cas, il y a probablement d'autres cotraitantes.
     - S'il n'y a que des sous-traitants, ne rien renvoyer.
     - Ne rien renvoyer si aucun nom de contratant trouvé.
     Format : une liste de dictionnaires sous format [{'nom': 'nom de la société', 'siret': 'siret de la société'}]
""",
        "search": "",
        "output_field": "cotraitants"
    },

    "sous_traitants":{
        "consigne": """SOUS_TRAITANTS
     Définition : Liste des sous-traitants du mandataire, s'il y en a.
     Indices : 
     - Rechercher dans le paragraphe de description du groupement, s'il y a plusieurs entreprises sous-traitantes (et non pas cotraitantes).
     - S'il n'y a que des cotraitants, ne rien renvoyer.
     - Ne rien renvoyer si aucun sous-traitant trouvé.
     Format : une liste de dictionnaires sous format [{'nom': 'nom de la société', 'siret': 'siret de la société'}]
""",
        "search": "Section du document qui décrit le groupement et les entreprises qui le composent.",
        "output_field": "sous_traitants"
    },

    "rib_autres":{
        "consigne": """RIB_AUTRES
     Définition : RIB des autres entreprises du groupement, s'il y en a.
     Indices : 
     - Rechercher dans le paragraphe des comptes à créditer, s'il y a plusieurs RIB indiqués pour plusieurs entreprises différentes..
     - S'il n'y a que le RIB du mandataire, ne rien renvoyer.
     Format : une liste de dictionnaires sous format [{'nom': 'nom de la société', 'IBAN': 'IBAN du compte à créditer'}]
""",
        "search": "Section du document qui décrit le groupement et les entreprises qui le composent.",
        "output_field": "rib_autres"
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

