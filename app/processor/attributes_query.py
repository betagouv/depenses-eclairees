import pandas as pd

# Attributs communs : objet, description_prestations, administration_beneficiaire, type_document, montant_ht, montant_ttc, date_creation, date_signature

DOC_ATTRS = {
   "devis": [
      "objet",
      "sujet", 
      "type_document",
      "montant_ht",
      "montant_ttc",
      "administration_beneficiaire",
      "description_prestations",
      "numero_devis", 
      "date_creation",
      "date_signature",
      "societe_principale",
      "siren", 
      "siret",
      "n_tva", 
   ],
   "acte_engagement": [
      "objet", 
      "type_document",
      "montant_ht",
      "montant_ttc",
      "administration_beneficiaire",
      "description_prestations",
      "societe_principale", 
      "siret", 
      "siren",  
      "date_signature"
   ],
   "avenant": [
      "objet", 
      "type_document",
      "montant_ht",
      "montant_ttc",
      "administration_beneficiaire",
      "description_prestations",
      "societe_principale", 
      "siret", 
      "siren",  
      "date_signature"
   ],
   "fiche_navette": [
      "administration_beneficiaire", 
      "objet", 
      "societe_principale", 
      "montant_ht", 
      "accord_cadre", 
      "id_accord_cadre"
   ],

   "cctp": [# à moderniser
      "titre", 
      "objet_marche", 
      "prestations", 
      "lots"
   ],

   "bon_de_commande": [
      "objet", 
      "type_document",
      "montant_ht",
      "montant_ttc",
      "administration_beneficiaire",
      "description_prestations",
      "date_signature",
      "societe_principale",
      "siren", 
      "siret",
   ],
   
   "sous_traitance": [
      "administration_beneficiaire",
      "objet_marche",
      "societe_principale",
      "adresse_postale_titulaire",
      "siret_titulaire",
      "societe_sous_traitant",
      "adresse_postale_sous_traitant",
      "siret_sous_traitant",
      "montant_sous_traitance_ht",
      "montant_sous_traitance_ttc",
      "description_prestations",
      "date_signature",
   ],

   "rib": [
      "iban",
      "bic",
      "titulaire_compte",
      "adresse_postale_titulaire",
      "domiciliation"
   ],

   "att_sirene": [
      "siret",
      "siren",
      "denomination_insee",
      "activite_principale",
      "adresse_postale_insee"
   ],

   "kbis":[
      "denomination_insee",
      "siren_kbis",
      "activite_principale",
      "adresse_postale_insee"
   ],

   "ccap":[
      "objet_marche_ccap",
      "lots_ccap",
      "forme_marche_ccap",
      "allottissement_ccap",
      "duree_lots_ccap",
      "duree_marche_ccap",
      "formule_revision_prix_ccap",
      "index_reference_ccap",
      "condition_avance_ccap",
      "revision_prix_ccap",
      "montant_ht_lots_ccap",
      "montant_ht_ccap",
      "ccag_ccap"
   ]

}

ATTRIBUTES_DEFS = {
   # type_document
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

   # numero_devis
   "numero_devis": {
      "consigne": """NUMERO_DEVIS
   - Chercher les mentions "N° de devis", "Devis n°", "Référence", "Réf."
   - Format typique : DEV12345, D-2023-123, etc.
   - Conserver exactement comme écrit, avec tirets ou autres séparateurs
   - Ne rien renvoyer si aucun identifiant trouvé
""",
      "search": "",
      "output_field": "numero_devis"
   },

   # siren
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

   # siren_kbis:
   "siren_kbis": {
      "consigne": """SIREN_KBIS
      Définition : Numéro SIREN de la personne morale dans l'extrait Kbis.
      Indices : 
      - Rechercher le numéro SIREN de la personne morale dans l'extrait Kbis.
      - A partir d'un numéro RCS : les 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
      - Ne rien renvoyer si aucun numéro SIREN trouvé.
""",
      "search": "",
      "output_field": "siren"
   },

   # siret
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

   "siret_titulaire": {
      "consigne": """SIRET_TITULAIRE  
   Définition : Numéro SIRET du titulaire principal du marché, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", "numéro d'immatriculation" ou "SIRET du titulaire"
   - Rechercher dans la section du titulaire principal du marché
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
      "search": "",
      "output_field": "siret_titulaire"
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
      "output_field": "siret_sous_traitant"
   },

   # n_tva
   "n_tva": {
      "consigne": """N_TVA
   Définition : numéro de TVA du prestataire / du titulaire principal
   Indices :
   - Chercher "N° TVA", "TVA intracommunautaire", "N° Intracommunautaire"
   - Format typique : FR12345678900, FRXX123456789
   - Conserver exactement comme écrit, avec tous les caractères
   - Ne rien renvoyer si aucun numéro TVA trouvé
   Format : un identifiant composé de 2 lettres et 11 chiffres, sans espaces ni caractères spéciaux.
""",
      "search": "",
      "output_field": "n_tva"
   },

   # montant_ht
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

   # montant_ttc
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
      "output_field": "montant_sous_traitance_ht"
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
      "output_field": "montant_sous_traitance_ttc"
   },
   
   # date_creation
   "date_creation": {
      "consigne": """DATE_CREATION
      Définition : Date de création, d'édition ou de rédaction du document.  
      Indices : 
      - Chercher au début du document près de "Date" (création), "Émis le" (émission), "Fait le" (rédaction), "Édité le" (édition)
      - Si plusieurs dates disponibles, privilégier celle d'émission/création
      - Ignorer les dates de signature en bas du document.
      - Ne rien renvoyer si aucune date trouvée
      Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine 
""",
      "search": "",
      "output_field": "date_creation"
   },

   # date_signature
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

   # titre
   "titre": {
      "consigne": """TITRE
   - Identifie UNIQUEMENT le titre principal du document.
   - Le titre est généralement en début de document, souvent mis en évidence (majuscules, gras, grande taille).
   - Ne donne que le titre exact, sans commentaire ni explication.
   - Si tu ne trouves pas de titre clair, extrait ce qui ressemble le plus à un titre.
   - Ne commence pas ta réponse par "Le titre est" ou "Titre:".        
""",
      "search": "titre principal du document en-tête première page",
      "output_field": "titre"
   },

   # description_prestations
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

   # objet
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

   # sujet
   "sujet": {
      "consigne": """SUJET
   Définition : sujet de la commande ou du marché, c'est-à-dire ce qui a été acheté, ou le service fourni.
   Indices :
   - Soit dans le titre du document, soit dans une section dédiée, ou dans le détail des prestations.
   - Dans tous les cas, le sujet de la commande doit avoir du sens pour une personne extérieure, et permettre de comprendre le contenu du document.
   - Ne rien renvoyer si aucun objet trouvé
   Format : 
   - En bon Français
   - Attention, ne pas inclure le type de document dans l'objet : "Devis pour ..." enlever "Devis pour" / "Avenant pour ..." enlever "Avenant pour".
   - Si l'objet du document est incompréhensible, proposer un objet de devis simple qui reflète le contenu des prestations.
""",
      "search": "",
      "output_field": "sujet"
   },

   # objet_marche
   "objet_marche": {
      "consigne": """OBJET_MARCHE
     Définition : Formulation synthétique de l'objet du marché.
     Indices : 
     - L'objet du marché peut être dans le titre directement, ou plus généralement dans une section dédiée.
     - Identifier les formules comme "Objet du marché", "Le marché a pour objet", ou toute expression indiquant l'intitulé de la mission.  
""",
      "search": "Section du document qui décrit l'objet du marché ou le contexte général de la consultation.",
      "output_field": "objet_marche"
   },

   # resume_prestations
   "description_courte": {
      "consigne": """DESCRIPTION_COURTE
     Définition : Description des prestations de la commande ou du marché la plus spécifique possible, structurée et compréhensible en moins de 10 mots.
     Indices : 
      - Un texte décrivant le contenu de la prestation, des services attendus ou réalisés, et du matériel utilisé ou acheté.
      - Des précisions si disponibles sur la date ou la période, le lieu de la prestation, les quantités sont bienvenues.
      - Attention à ne pas renvoyer de données personnelles (nom, prénom, adresse postales ou coordonnées).
      - Attention à ne pas renvoyer de détails de prix.
      Format : en bon Français, reformulé si besoin, en moins de 10 mots.""",
      "search": "",
      "output_field": "description_courte"
   },

   # prestations
   "prestations": {
      "consigne": """PRESTATIONS
   - Crée un résumé CONCIS des prestations techniques attendues dans le cadre de ce marché.
   - Concentre-toi uniquement sur les actions concrètes à réaliser ou les livrables attendus.
   - Le résumé doit être direct et descriptif, sans contexte ni introduction.
   - Utilise un style factuel et synthétique en une seule phrase complète.
   - N'utilise pas de formulations comme "Ce marché concerne..." ou "Les prestations comprennent...".   
""",
      "search": "description des prestations, liste des livrables, contenu du marché, spécifications",
      "output_field": "prestations"
   },

   # lots
   "lots": {
      "consigne": """LOTS:
   - Vérifie la présence d'informations indiquant que le marché est divisé en plusieurs lots distincts.
   - Identifie et liste TOUS les intitulés/titres des différents lots du marché.
   - Présente-les sous forme d'une liste séparée par des points-virgules (;).
   - Chaque titre de lot doit être précédé par "Lot N°X: " ou son équivalent si le numéro est mentionné.
   - Si le numéro n'est pas mentionné, liste simplement le titre du lot.
   - Réponds uniquement si le marché est alloti.
   - Ne donne aucune explication ou commentaire supplémentaire.
   - Exemple de format attendu: "Lot N°1: Gros œuvre; Lot N°2: Peinture; Lot N°3: Électricité"
""",
      "search": "La décomposition du marché en plusieurs lots, la liste des lots et de leurs principales prestations.",
      "output_field": "lots"
   },

   # administration_bénéficiaire
   "administration_bénéficiaire": {
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

   # societe_principale
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


   "societe_sous_traitant": {
      "consigne": """SOCIETE_SOUS_TRAITANT  
     Définition : Société sous-traitante qui réalise une partie des prestations du marché.  
     Indices : 
     - Rechercher les mentions de société, entreprise, sous-traitant dans la section dédiée à la sous-traitance.
     - Le nom de la société sous-traitante est généralement distinct de la société principale.
     Format : renvoyer le nom de la société sous-traitante telle qu'écrit dans le document.
""",
      "search": "",
      "output_field": "societe_sous_traitant"
   },

   # accord_cadre
   "accord_cadre": {
      "consigne": """accord_cadre  
     Définition : Libellé de l'accord-cadre
     Indices : Repérer les expressions comme "Libellé accord-cadre".  
""",
      "search": "",
      "output_field": "accord_cadre"
   },
   
   # id_accord_cadre
   "id_accord_cadre": {
      "consigne": """id_accord_cadre  
     Définition : Identifiant de l'accord cadre 
     Indices : Repérer les identifiants sous la forme "2022AMO0538402"
""",
      "search": "",
      "output_field": "id_accord_cadre"
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
      "output_field": "adresse_postale_sous_traitant"
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

   # adresse_postale_insee
   "adresse_postale_insee":{
      "consigne": """ADRESSE_POSTALE_INSEE
     Définition : Adresse postale de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher l'adresse postale de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune adresse postale trouvée.
""",
      "search": "",
      "output_field": "adresse_postale_insee"
   },

   # iban
   "iban":{
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

   # bic
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

   # titulaire_compte
   "titulaire_compte":{
      "consigne": """TITULAIRE_COMPTE
     Définition : Nom du titulaire du compte bancaire.
     Indices : 
     - Rechercher le nom du titulaire du compte bancaire dans la section du RIB.
     - Ne rien renvoyer si aucun nom de titulaire trouvé.
""",
      "search": "",
      "output_field": "titulaire_compte"
   },

   # domiciliation
   "domiciliation":{
      "consigne": """DOMICILIATION
     Définition : Domiciliation du compte bancaire.
     Indices : 
     - Rechercher la domiciliation du compte bancaire dans la section du RIB.
     - Ne rien renvoyer si aucune domiciliation trouvée.
""",
      "search": "",
      "output_field": "domiciliation"
   },

   # denomination_insee
   "denomination_insee":{
      "consigne": """DENOMINATION_INSEE
     Définition : Dénomination de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher la dénomination de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune dénomination trouvée.
""",
      "search": "",
      "output_field": "denomination"
   },

   # activite_principale
   "activite_principale":{
      "consigne": """ACTIVITE_PRINCIPALE
     Définition : Activité principale exercée (APE) de la société dans le répertoire SIRENE.
     Indices : 
     - Rechercher l'activité principale de la société dans le répertoire SIRENE.
     - Ne rien renvoyer si aucune activité principale trouvée.
""",
      "search": "",
      "output_field": "activite_principale"
   },
   
   # alottissement
   "allottissement_ccap": {
      "consigne": """ALLOTTISSEMENT
     Définition : Allotissement du marché ou décomposition en lots.
     Indices : 
     - Souvent dans une section dédiée, dans les premiers articles du document.
     - S'il y a plusieurs lots décrits, alors le marché est alloti.
     Format : True si le marché est alloti, False sinon.
""",
      "search": "",
      "output_field": "allottissement"
   },

   # montant_ht_lots_ccap
   "montant_ht_lots_ccap": {
      "consigne": """MONTANT_HT_LOTS_CCAP
     Définition : Montant de chaque lot du marché.
     Indices : 
     - Dans la section spécifique des montants du marché, ou dans la forme du marché.
     - Si le marché est alloti, alors il y a un montant pour chaque lot.
     - Si le marché n'est pas alloti, renvoyer une liste vide.
     - Si les montants HT sont annuels, il faut préciser le montant suivi de "HT/an".
     - Si les montants HT sont globaux, il faut préciser le montant suivi de "HT total".
     Format : une liste au format python ["Lot 1 : [montant]", "Lot 2 : [montant]", ...].
""",
      "search": "",
      "output_field": "montant_ht_lots"
   },
   
      # montants_ht_ccap
      "montants_ht_ccap": {
         "consigne": """MONTANT_HT_CCAP
      Définition : Montant global du marché pour un marché non alloti.
      Indices : 
     - Dans la section spécifique des montants du marché, ou dans la forme du marché.
     - Si le marché est alloti, ne rien renvoyer.
     - Si les montants HT sont annuels, il faut préciser le montant suivi de "HT/an".
     - Si les montants HT sont globaux, il faut préciser le montant suivi de "HT total".
     Format : le montant en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales) suivi de HT/an ou HT total.
""",
      "search": "",
      "output_field": "montants_ht"
      },
   
   # lots_ccap
   "lots_ccap": {
      "consigne": """LOTS_CCAP
     Définition : Liste des lots du marché.
     Indices : 
     - Rechercher les lots du marché dans la section de l'alotissement.
     - Si une décomposition en lots est mentionnée ailleurs dans le document, alors renvoyer la liste des lots avec les informations trouvées.
     Format : une liste au format python ["Lot 1 : [intitulé]", "Lot 2 : [intitulé]", ...].
""",
      "search": "",
      "output_field": "lots"
   },

   # forme_marche_ccap
   "forme_marche_ccap": {
      "consigne": """FORME_MARCHE_CCAP
     Définition : La forme de passation des commandes de ce marché spécifique, et le nombre d'attributaires.
     Indices : 
     - Rechercher la forme du marché dans un paragraphe sur la passation des commandes.
     - Le marché peut être : à marchés subséquents, à bons de commande, mixte et dans chaque cas mono-attributaire ou multi-attributaire.
     - Par défaut, les marchés sont à bons de commande mono-attributaires.
     - S'il y a un paragraphe sur le format des bons de commande le marché est à bons de commande.
     - S'il y a mention de marchés subséquents à ce marché, alors le marché est à marchés subséquents.
     Format : "à marchés subséquents", "à bons de commande", "mixte" suivi de "mono-attributaire" ou "multi-attributaire" si le nombre d'attributaires est mentionné.
   """,
      "search": "",
      "output_field": "forme_marche_ccap"
   },

   # duree_lots_ccap
   "duree_lots_ccap": {
      "consigne": """DUREE_LOTS
     Définition : Durée de chaque lot du marché.
     Indices : 
     - Dans la section spécifique de la durée du marché.
     - Si le marché est alloti, alors il y a une durée pour chaque lot.
     - Si le marché n'est pas alloti, renvoyer une liste vide.
     Format : une liste au format python ["Lot 1 : [durée]", "Lot 2 : [durée]", ...].
""",
      "search": "",
      "output_field": "duree_lots"
   },
   
   # duree_marche_ccap
   "duree_marche_ccap": {
      "consigne": """DUREE_MARCHE_CCAP
     Définition : Durée du marché pour un marché non alloti.
     Indices : 
     - Dans la section spécifique de la durée du marché.
     - Si le marché est alloti, ne rien renvoyer.
     Format : en nombre de mois.
""",
      "search": "",
      "output_field": "duree_marche"
   },

   # revision_prix_ccap
   "revision_prix_ccap": {
      "consigne": """REVISION_PRIX
     Définition : Les prix sont révisables ou fermes.
     Indices : 
     - Dans la section spécifique de la formule de révision des prix.
     - Si les prix sont fermes, renvoyer "Prix fermes".
     - Sinon, renvoyer "Prix révisables".
""",
      "search": "",
      "output_field": "revision_prix"
   },


   # formule_revision_prix_ccap
   "formule_revision_prix_ccap": {
      "consigne": """FORMULE_REVISION_PRIX
     Définition : Formule de révision des prix
     Indices : 
     - Dans la section spécifique de la formule de révision des prix.
     - La formule de révision est souvent de la forme "C = ..."
     Format : [la formule mathématiques de révision des prix, la définition des variables]
""",
      "search": "",
      "output_field": "formule_revision_prix"
   },

   # index_reference_ccap
   "index_reference_ccap": {
      "consigne": """INDEX_REFERENCE_CCAP
     Définition : Index de référence
     Indices : 
     - Dans une section spécifique de l'index de référence.
     Format : le nom de l'index de référence.
""",
      "search": "",
      "output_field": "index_reference"
   },

   # condition_avance_ccap
  "condition_avance_ccap": {
    "consigne": """CONDITIONS_AVANCE
   Définition : Conditions de déclenchement et calcul du montant de l'avance à payer.
   Indices :
   - Rechercher les conditions de montant minimum HT et durée minimum, s'il y en a. Sinon, renvoyer "Avance systématique".
   - Trouver le montant de l'avance en %.
   - Trouver le montant de référence pour le calcul de l'avance (bon de commande, montant annuel, montant minimum HT, ...).
   - Repérer les seuils de remboursement (début et fin)
   - Si pour le remboursement, il est fait référence uniquement au code de la commande publique (R.2191-11) :
      - Pour des montants <= 30% du marché TTC, c'est à partir de 65% du montant TTC que le remboursement se déclenche. Renvoyer "65%".
      - Pour des montants > 30% du marché TTC, c'est dès le premier paiement. Renvoyer "0%".
   Format : condition_déclenchement:"", montant_avance:XX%, montant_reference:"", remboursement:XX%-XX%
""",
    "search": "avance accordée titulaire montant initial durée exécution remboursement précompte",
    "output_field": "condition_avance_ccap"
   },

   # objet_marche_ccap
   "objet_marche_ccap": {
    "consigne": """OBJET_MARCHE_CCAP
     Définition : Formulation synthétique de l'objet du marché.
     Indices : 
     - L'objet du marché peut être dans le titre directement, ou plus généralement dans une section dédiée.
     - Identifier les formules comme "Objet du marché", "Le marché a pour objet", ou toute expression indiquant l'intitulé de la mission.  
""",
      "search": "Section du document qui décrit l'objet du marché ou le contexte général de la consultation.",
      "output_field": "objet_marche_ccap"
   
   },

   # ccag_ccap
   "ccag_ccap": {
    "consigne": """CCAG
     Définition : Le CCAG en vigueur pour ce marché.
     Indices : 
     - Le CCAG s'appliquant sur le maché est de la forme CCAG-XXXX. Le XXXXXX est l'acronyme du CCAG.
     - Ne rien renvoyer si aucun CCAG n'est mentionné.
     Format : CCAG-XXXX.
""",
      "search": "",
      "output_field": "ccag"
   
   },
}

# Génère le DataFrame ATTRIBUTES avec la colonne "type_attachments" (liste des types concernés)
rows = []
for attr, attr_def in ATTRIBUTES_DEFS.items():
    types = [doc_type for doc_type, attrs in DOC_ATTRS.items() if attr in attrs]
    rows.append({
        "attribut": attr,
        "consigne": attr_def.get("consigne", ""),
        "search": attr_def.get("search", ""),
        "output_field": attr_def.get("output_field", attr),
        "type_attachments": types
    })

ATTRIBUTES = pd.DataFrame(rows)

def select_attr(df_attributes, doc_type):
    """
    Sélectionne les lignes du DataFrame ATTRIBUTES correspondant à un type de document donné.
    Args:
        df_attributes (pd.DataFrame): DataFrame des attributs (avec colonne 'type_attachments')
        doc_type (str): Type de document à filtrer (ex: 'devis', 'cctp', ...)
    Returns:
        pd.DataFrame: Sous-ensemble du DataFrame avec les attributs du type demandé
    """
    return df_attributes[df_attributes['type_attachments'].apply(lambda types: doc_type in types)]
