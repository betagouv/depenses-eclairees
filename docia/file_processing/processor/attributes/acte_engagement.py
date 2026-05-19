"""
Définitions des attributs à extraire pour les documents de type "acte_engagement".
"""

from .common import (
    ADMINISTRATION_BENEFICIAIRE,
    CONSERVE_AVANCE,
    MONTANT_HT,
    MONTANT_TTC,
    MONTANT_TVA,
    OBJET_MARCHE,
    SCHEMA_DUREE,
    SCHEMA_LISTE_ENTREPRISE_SIRET,
    SCHEMA_RIB,
    SOCIETE_PRINCIPALE,
)

ACTE_ENGAGEMENT_ATTRIBUTES = {
    "objet_marche": OBJET_MARCHE,
    "forme_marche": {
        "consigne": """
   Définition : Informations sur la forme du marché concernant les lots, les marchés subséquents et les marchés parents.
   Indices :
   - Chercher après les mentions "Objet", "Lot", "marché subséquent", "marché parent", ou autres mentions similaires, en particulier en début du document.
   - Pour le champ lot_concerne :
     * Si le marché concerne un lot spécifique, identifier le numéro du lot (chercher "Lot X", "Lot n°X", etc.) et son titre. Si pas de titre explicite trouvée, renvoyer null pour titre_lot.
     * Si le marché n'est pas un lot, renvoyer null pour numero_lot et titre_lot.
   - Pour le champ marche_subsequent :
     * Rechercher les mentions explicites de "marché subséquent", "marchés subséquents", ou formulations équivalentes.
     * Si le document précise que ce marché est un marché subséquent ou fait partie d'un marché à marchés subséquents, renvoyer true.
     * Sinon, renvoyer false.
   - Pour le champ marche_parent :
     * Rechercher l'identifiant du marché parent (souvent mentionné après "accord-cadre", "contrat-cadre", "marché global", etc.).
     * L'identifiant peut être un numéro de marché, un code, un numéro de consultation ou toute référence unique au marché parent. Exemple 22_BAM_035, ou SIG_AOO_2021_07
     * Ne pas inclure ATTRI1, n°Chorus, 1300000000 ou 2025.1000000000, uniquement le numéro (pas de parenthèses de précision). Pas de reformulation.
     * Si aucun marché parent n'est mentionné ou si son identifiant n'est pas disponible, renvoyer null.
   Format : 
   - Un objet JSON avec les trois champs suivants au même niveau :
     * "lot_concerne" : objet avec "numero_lot" (entier ou null) et "titre_lot" (chaîne ou null)
     * "marche_subsequent" : booléen (true ou false)
     * "marche_parent" : chaîne (identifiant du marché parent) ou null
""",
        "schema": {
            "type": "object",
            "properties": {
                "lot_concerne": {
                    "type": ["object", "null"],
                    "properties": {
                        "numero_lot": {"type": ["integer", "null"]},
                        "titre_lot": {"type": ["string", "null"]},
                    },
                    "required": ["numero_lot", "titre_lot"],
                },
                "marche_subsequent": {"type": "boolean"},
                "marche_parent": {"type": ["string", "null"]},
            },
            "required": ["lot_concerne", "marche_subsequent", "marche_parent"],
        },
    },
    "administration_beneficiaire": ADMINISTRATION_BENEFICIAIRE,
    "societe_principale": SOCIETE_PRINCIPALE,
    "siret_mandataire": {
        "consigne": """
   Définition : Numéro SIRET de la société principale, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", ou "numéro d'immatriculation".
   - Favoriser les numéros de SIRET indiqués dans l'identification du titulaire, plutôt qu'en signature du document.
   - Si plusieurs SIRET sont disponibles pour une même entreprise, avec différentes terminaisons (5 derniers chiffres) :
        * Prendre le numéro de l'établissement concerné (pas le siège social) pour renvoyer le SIRET.
        * S'il n'y a pas de précisions sur l'établissement concerné, renvoyer le SIRET le plus élevé.
            -> Exemple : 123 456 789 00001 et 123 456 789 00020, renvoyer 12345678900020 (car 00020 > 00001).
   - Si le numéro de SIRET ne contient pas suffisamment de caractères, ne pas compléter : renvoyer tel quel.
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
    },
    "siren_mandataire": {
        "consigne": """
   Définition : numéro de SIREN du prestataire / du titulaire principal, composé de 9 chiffres
   Indices :
   - Après la mention SIREN au début ou à la fin du document.
   - A partir d'un numéro de SIRET : les 9 premiers chiffres d'un SIRET de 14 chiffres.
   - A partir d'un numéro RCS : les 9 chiffres du numéro RCS (après "RCS" ou "N° RCS")
   - A partir d'un numéro de TVA : les 9 derniers chiffres du numéro de TVA (après l'identifiant du pays et du département ex : FR12)
   - Ne rien renvoyer si aucun SIREN trouvé
   Format : un numéro composé de 9 chiffres, sans espaces ni caractères spéciaux
""",
    },
    "rib_mandataire": {
        "consigne": """
     Définition : Informations bancaires (IBAN en priorité) du compte à créditer indiqué dans l'acte d'engagement.
     Indices : 
     - Rechercher dans les informations bancaires, en priorité près des mentions "RIB" ou "IBAN".
     - 1er cas (prioritaire) : l'IBAN est fourni (27 caractères commençant par "FR76" pour un RIB français). Renvoyer :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'iban' : IBAN du compte à créditer (souvent 6 groupes de 4 caractères, puis 3 caractères)
     - 2ème cas (uniquement s'il n'y a pas d'IBAN) : l'IBAN n'est pas fourni, mais les autres informations bancaires sont fournies. Renvoyer :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'code_banque' : code de la banque à 5 chiffres (espaces non compris)
        * 'code_guichet' : code du guichet à 5 chiffres (espaces non compris)
        * 'numero_compte' : numéro de compte français à 11 chiffres (espaces non compris)
        * 'cle_rib' : clé du RIB à 2 chiffres (espaces non compris)
     - Si aucune information bancaire trouvée pour le mandataire (ni IBAN, ni informations seules), renvoyer {}
     - Si un seul numéro à 11 chiffres est fourni, il s'agit souvent du numero de compte. Exemple: Numéro de compte: 12345678901. Renvoyer le numéro de compte seul.
     Format : 
     - 1er cas (prioritaire) : un json sous format suivant {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}
     - 2ème cas (secondaire - uniquement s'il n'y a pas d'IBAN) : un json sous format suivant {"banque": "nom de la banque", "code_banque": "code de la banque à 5 chiffres", "code_guichet": "code du guichet à 5 chiffres", "numero_compte": "numéro de compte à 11 chiffres", "cle_rib": "clé du RIB à 2 chiffres"}
""",
        "schema": SCHEMA_RIB,
    },
    "cotraitants": {
        "consigne": """
Objectif : Extraire uniquement les entreprises réellement mentionnées comme cotraitantes (hors mandataire).
Règles d’extraction :
- Ne retenir qu’une entreprise explicitement décrite comme cotraitante dans le texte.
- Ignorer totalement les entreprises mentionnées comme sous-traitantes.
- Ignorer toute mention générique contenant le mot “cotraitant” (ex. “Cotraitant”, “cotraitant1”, “cotraitant2”) : ce ne sont pas des entreprises.
- Une entreprise n’est retenue que si au moins l’un des éléments suivants apparaît dans le texte : un nom réel d’entreprise, un numéro SIRET (14 chiffres) ou SIREN (9 chiffres) valide.
- Pour le nom (champ "nom") : en cas de choix, préférer la raison sociale plutôt que le nom commercial.
- Pour le SIRET (champ "siret") : si plusieurs SIRET sont disponibles pour une même entreprise :
    * Prendre le numéro de l’établissement concerné (pas le siège social) pour renvoyer le SIRET.
    * S'il n’y a pas de précisions sur l’établissement concerné, renvoyer le SIRET le plus élevé.
- Si aucun cotraitant réel n’est identifié dans le texte, renvoyer []
- Format attendu : 
    * une liste JSON : [{"nom": "...", "siret": "..."}]
    * Si aucun cotraitant valide n’est trouvé, renvoyer exactement : []
""",
        "schema": SCHEMA_LISTE_ENTREPRISE_SIRET,
    },
    "sous_traitants": {
        "consigne": """
     Définition : Liste des sous-traitants du mandataire, s'il y en a.
     Indices : 
     - Rechercher dans le paragraphe de description du groupement, s'il y a plusieurs entreprises sous-traitantes (et non pas cotraitantes).
     - S'il n'y a que des cotraitants, ne rien renvoyer.
     - Ne rien renvoyer si aucun sous-traitant trouvé.
     Format : une liste de dictionnaires sous format [{"nom": "nom de la société", "siret": "siret de la société"}]
""",
        "schema": SCHEMA_LISTE_ENTREPRISE_SIRET,
    },
    "rib_autres": {
        "consigne": """
     Définition : RIB des autres entreprises du groupement (cotraitants, etc.), s'il y en a. Informations bancaires (IBAN en priorité) du compte à créditer pour chaque entreprise.
     Indices : 
     - Rechercher dans le paragraphe des comptes à créditer, s'il y a plusieurs RIB indiqués pour plusieurs entreprises différentes.
     - Pour chaque entreprise (autre que le mandataire), renvoyer 'societe' (nom cohérent avec le champ cotraitants si possible) et 'rib' :
     - 1er cas (prioritaire) : l'IBAN est fourni (27 caractères commençant par "FR76"). Renvoyer dans 'rib' :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'iban' : IBAN du compte à créditer (souvent 6 groupes de 4 caractères, puis 3 caractères)
     - 2ème cas (uniquement s'il n'y a pas d'IBAN) : l'IBAN n'est pas fourni, mais les autres informations bancaires sont fournies. Renvoyer dans 'rib' :
        * 'banque' : Nom de la banque (sans la mention "Banque")
        * 'code_banque' : code de la banque à 5 chiffres (espaces non compris)
        * 'code_guichet' : code du guichet à 5 chiffres (espaces non compris)
        * 'numero_compte' : numéro de compte français à 11 chiffres (espaces non compris)
        * 'cle_rib' : clé du RIB à 2 chiffres (espaces non compris)
     - S'il n'y a que le RIB du mandataire, renvoyer [].
     - S'il n'y a pas d'informations sur le compte bancaire pour une entreprise (ni IBAN, ni informations RIB), ne pas inclure cette entreprise dans la liste.
     - Si un seul numéro à 11 chiffres est fourni, il s'agit souvent du numero de compte. Exemple: Numéro de compte: 12345678901. Renvoyer le numéro de compte seul.
     Format : 
     - 1er cas (prioritaire) : [{"societe": "nom de la société", "rib": {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}}]
     - 2ème cas (secondaire - uniquement s'il n'y a pas d'IBAN) : [{"societe": "nom de la société", "rib": {"banque": "nom de la banque", "code_banque": "...", "code_guichet": "...", "numero_compte": "...", "cle_rib": "..."}}]
""",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "societe": {"type": "string"},
                    "rib": {
                        "type": "object",
                        "properties": {
                            "banque": {"type": ["string", "null"]},
                            "iban": {"type": ["string", "null"]},
                            "code_banque": {"type": ["string", "null"]},
                            "code_guichet": {"type": ["string", "null"]},
                            "numero_compte": {"type": ["string", "null"]},
                            "cle_rib": {"type": ["string", "null"]},
                        },
                    },
                },
                "required": ["societe", "rib"],
            },
        },
    },
    "montant_ht": MONTANT_HT,
    "montant_ttc": MONTANT_TTC,
    "duree": {
        "consigne": """
        Définition : Durée du marché totale exprimée en mois et extension possible.
        Indices :
        - Chercher dans le paragraphe indiquant la durée du marché ou le délai d'exécution des prestations.
        - Durée initiale : la durée du marché ferme (sans reconduction ou tranches optionnelles), en nombre de mois.
            * En l'absence de précisions sur la durée ferme, par exemple s'il y a seulement des dates de début et de fin, renvoyer duree_initiale: null
            * Exemple : une durée de 1 an, renvoyer 12.
        - Extension de durée possible : extenion maximale en nombre de mois.
            * En l'absence d'informations claires, renvoyer duree_reconduction: null
            * Si des reconductions sont précisées (ne pas confondre avec des tranches optionnelles qui sont gérées ci-dessous) :
                1. duree_reconduction : Trouver la durée d'une reconduction (en nombre de mois). Si l'information n'est pas précisée ou qu'il n'y a pas de reconduction, renvoyer null.
                2. nb_reconductions : Trouver le nombre de reconductions possibles. Si l'information n'est pas précisée ou qu'il n'y a pas de reconduction, renvoyer null.
            * Si des tranches optionnelles sont précisées : renvoyer la durée de l'ensemble des tranches optionnelles.
                1. delai_tranche_optionnelle : Trouver la durée de l'ensemble des tranches optionnelles. Si l'information n'est pas précisée ou qu'il n'y a pas de tranches optionnelles, renvoyer null.
                    Exemple : 2 tranches optionnelles de 8 mois, renvoyer 8 + 8 = 16.
        Format : un json sous format suivant {"duree_initiale": "nombre entier de mois", "duree_reconduction": "nombre entier de mois", "nb_reconductions": "nombre entier de reconductions possibles", "delai_tranche_optionnelle": "nombre entier de mois"}
    """,
        "schema": SCHEMA_DUREE,
    },
    "date_signature_mandataire": {
        "consigne": """
      Définition : Date de signature du document par le mandataire (entreprise prestataire principale). 
      Indices : 
      - Uniquement la date de signature de l'entreprise mandataire, pas celle de l'administration bénéficiaire.
      - Souvent la première date de signature en cas de plusieurs dates de signature.
      - Repérer les expressions comme "Signé le", "Fait à ...", ou des dates en bas du document associées à une signature.
        * Si une date est indiquée après "date de signature" ou "Signé le", on considère le document comme signé,
         même si la signature n'apparaît pas dans le texte extrait.
      - Si le document termine par une date seule, c'est probablement la date de signature de l'administration.
      - Ignorer les dates d'émission ou de création du document, en général en haut du document
      - Ne rien renvoyer si aucune date de signature trouvée pour le mandataire.
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
    },
    "date_signature_administration": {
        "consigne": """
      Définition : Date de signature du document par l'administration. 
      Indices : 
      - Uniquement la date de signature de l'acheteur, du pouvoir adjudicateur, ou de l'administration bénéficiaire.
      - Souvent la dernière signature en cas de plusieurs dates de signatures.
      - Repérer les expressions comme "Signé le", "Fait à ...", "signature électronique", ou des dates en bas du document associées à une signature.
        * Si une date est indiquée après "date de signature" ou "Signé le", on considère le document comme signé,
         même si la signature n'apparaît pas dans le texte extrait.
      - Si le document termine par une date seule, c'est surement la date designature de l'administration.
      - Parfois la signature est électronique : seuls le nom du signataire et la date apparaissent dans le texte. 
      - Ignorer les dates d'émission ou de création du document, en général en haut du document
      - Ne rien renvoyer si aucune date de signature trouvée
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
    },
    "date_notification": {
        "consigne": """
      Définition : Date de notification du marché aux mandataires. 
      Indices : 
      - Parfois en début du document, ou en toute fin de document.
      - Après la mention "Date de notification" mais ce n'est pas la date de début prévisionnelle "Date de début du marché".
      - S'il y a un doute sur la lecture de la date, prendre la date la plus proche postérieure à la signature par l'administration si disponible.
      - Peut aussi être la date d'un courrier de notification ou d'un mail en annexe du document.
      - S'il n'y a pas de date de notification explicite, ne rien renvoyer.
      - Attention à ne pas confondre la date de notification avec la date de signature.
      - Pour un marché subséquent, ne pas confondre avec la date de notification du marché (parent).
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
    },
    "conserve_avance": CONSERVE_AVANCE,
    "montants_en_annexe": {
        "consigne": """
     Définition : Indique si les montants sont précisés dans un autre document en annexe (uniquement ou en complément).
     Indices : 
     - Dans le paragraphe de l'engagement du titulaire, près de la mention des prix sur lesquels le titulaire s'engage.
     - Souvent sous forme d'une case à cocher suivi de la mention "au prix indiqué dans les autres documents annexés ...".
        * Une case cochée peut être représentée par [X], [x], X, x, ☒ ou autre équivalent.
        * Une case non cochée peut être représentée par [ ], un espace ou autre équivalent.
     - Si la mention est cochée ou qu'il est affirmé que les montants sont précisés en annexe, renvoyer :
        * "annexe_financière": true
        * "classification": une liste des types de documents mentionnés parmi : "BPU" (correspond aussi à bordereau de prix unitaires), "DPGF", "Annexe financière".
     - Si la mention n'est pas cochée ou qu'il est affirmé que les montants sont précisés dans le document uniquement, renvoyer :
        * "annexe_financière": false
        * "classification": null
""",
        "schema": {
            "type": "object",
            "properties": {
                "annexe_financière": {"type": ["boolean", "null"]},
                "classification": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "string",
                        "enum": ["BPU", "DPGF", "Annexe financière"],
                    },
                },
            },
            "required": ["annexe_financière", "classification"],
        },
    },
    "code_cpv": {
        "consigne": """
        Définition : Code CPV (catégorie de dépense du marché).
        - Chercher "CPV", "Code CPV" ; format type 8 chiffres (optionnel + tiret + chiffre), éventuellement suivi de l'intitulé du code.
        - Ex. 72611000-6 - Fournitures
        Si plusieurs : priorité au CPV principal, sinon tous séparés par des ";" 
        Format : "XXXXXXXX-X Intitulé" ou "XXXXXXXX Intitulé". Sinon null.""",
    },
    "montant_tva": MONTANT_TVA,
    "mode_consultation": {
        "consigne": """
        Définition : Mode de passation du marché (procédure adaptée, appel d'offres, MAPA, etc.).
        Chercher dans intro, préambule ou visas. Extraire la citation exacte du document, sans reformuler. Sinon null.""",
    },
    "mode_reconduction": {
        "consigne": """
        Définition : Reconduction du marché : expresse ou tacite ou null.
        - Sous la forme d'une case cochée ou explicitement mentionné dans le document.
        - Chercher "reconduction expresse", "reconduction tacite", "reconduit tacitement". Renvoyer "expresse" ou "tacite" si explicite.
        - Si aucune case cochée, et aucune mention renvoyer null.""",
        "schema": {
            "type": "string",
            "enum": ["expresse", "tacite", "null"],
        },
    },
    "ligne_imputation_budgetaire": {
        "consigne": """
        Définition : Ligne budgétaire d’imputation de la dépense.
        Chercher "imputation budgétaire", "ligne budgétaire", "chapitre", "article". Format type : chiffres/lettres/tirets (ex. 0723-CDIE).
        Ne pas confondre avec référence de marché. Sinon null.""",
    },
    "remise_catalogue": {
        "consigne": """
        Définition : Remise dans le catalogue.
        - Remise sur le catalogue proposée par le fournisseur titulaire.
        - Sous la d'un pourcentage à renvoyer tel quel (ex. 10 pour cent -> renvoyer "10").
        - Si aucune case cochée, et aucune mention renvoyer null.""",
    },
}
