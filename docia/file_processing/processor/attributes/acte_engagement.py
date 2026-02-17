"""
Définitions des attributs à extraire pour les documents de type "acte_engagement".
"""

ACTE_ENGAGEMENT_ATTRIBUTES = {
    "objet_marche": {
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
        "output_field": "objet_marche",
    },
    "forme_marche": {
        "consigne": """FORME MARCHE
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
     * Rechercher l'identifiant du marché parent (souvent mentionné comme "accord-cadre", "contrat-cadre", "marché global", etc.).
     * L'identifiant peut être un numéro de marché, un code, un numéro de consultation ou toute référence unique au marché parent.
     * Si aucun marché parent n'est mentionné ou si son identifiant n'est pas disponible, renvoyer null.
   Format : 
   - Un objet JSON avec les trois champs suivants au même niveau :
     * "lot_concerne" : objet avec "numero_lot" (entier ou null) et "titre_lot" (chaîne ou null)
     * "marche_subsequent" : booléen (true ou false)
     * "marche_parent" : chaîne (identifiant du marché parent) ou null
""",
        "search": "",
        "output_field": "forme_marche",
        "schema": {
            "type": "object",
            "properties": {
                "lot_concerne": {
                    "type": ["object", "null"],
                    "properties": {
                        "numero_lot": {
                            "type": ["integer", "null"]
                        },
                        "titre_lot": {
                            "type": ["string", "null"]
                        }
                    },
                    "required": ["numero_lot", "titre_lot"]
                },
                "marche_subsequent": {
                    "type": "boolean"
                },
                "marche_parent": {
                    "type": ["string", "null"]
                }
            },
            "required": ["lot_concerne", "marche_subsequent", "marche_parent"]
        },
    },
    "administration_beneficiaire": {
        "consigne": """ADMINISTRATION_BENEFICIAIRE 
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
        "search": "",
        "output_field": "administration_beneficiaire",
    },
    "societe_principale": {
        "consigne": """SOCIETE_PRINCIPALE  
     Définition : Société principale contractante (titulaire). Si un groupement est mentionné, extraire la société mandataire ou représentante.  
     Indices : 
     - Rechercher les mentions de société, entreprise, titulaire, mandataire, contractant.
     - En général, l'autre nom de personne morale que l'administration acheteuse.
     - Les noms de domaine des adresses mails peuvent donner des indices sur la bonne orthographe.
     Format : renvoyer le nom de la société.
""",
        "search": "",
        "output_field": "societe_principale",
    },
    "siret_mandataire": {
        "consigne": """SIRET_MANDATAIRE  
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
        "search": "",
        "output_field": "siret_mandataire",
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
        "output_field": "siren_mandataire",
    },
    "rib_mandataire": {
        "consigne": """RIB_MANDATAIRE
     Définition : Informations bancaires (IBAN en priorité) du compte à créditer indiqué dans l'acte d'engagement.
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
     - Si aucune information bancaire trouvée pour le mandataire (ni IBAN, ni informations seules), renvoyer {}
     Format : 
     - 1er cas (prioritaire) : un json sous format suivant {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}
     - 2ème cas (secondaire - uniquement s'il n'y a pas d'IBAN) : un json sous format suivant {"banque": "nom de la banque", "code_banque": "code de la banque à 5 chiffres", "code_guichet": "code du guichet à 5 chiffres", "numero_compte": "numéro de compte à 11 chiffres", "cle_rib": "clé du RIB à 2 chiffres"}
""",
        "search": "",
        "output_field": "rib_mandataire",
        "schema": {
            "type": "object",
            "properties": {
                "banque": {"type": ["string","null"]},
                "iban": {"type": ["string","null"]},
                "code_banque": {"type": ["string","null"]},
                "code_guichet": {"type": ["string","null"]},
                "numero_compte": {"type": ["string","null"]},
                "cle_rib": {"type": ["string","null"]}
            }
        },
    },
    "cotraitants": {
        "consigne": """COTRAITANTS
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
        "search": "",
        "output_field": "cotraitants",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"nom": {"type": "string"}, "siret": {"type": "string"}},
                "required": ["nom", "siret"],
            },
        },
    },
    "sous_traitants": {
        "consigne": """SOUS_TRAITANTS
     Définition : Liste des sous-traitants du mandataire, s'il y en a.
     Indices : 
     - Rechercher dans le paragraphe de description du groupement, s'il y a plusieurs entreprises sous-traitantes (et non pas cotraitantes).
     - S'il n'y a que des cotraitants, ne rien renvoyer.
     - Ne rien renvoyer si aucun sous-traitant trouvé.
     Format : une liste de dictionnaires sous format [{"nom": "nom de la société", "siret": "siret de la société"}]
""",
        "search": "Section du document qui décrit le groupement et les entreprises qui le composent.",
        "output_field": "sous_traitants",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"nom": {"type": "string"}, "siret": {"type": "string"}},
                "required": ["nom", "siret"],
            },
        },
    },
    "rib_autres": {
        "consigne": """RIB_AUTRES
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
     Format : 
     - 1er cas (prioritaire) : [{"societe": "nom de la société", "rib": {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}}]
     - 2ème cas (secondaire - uniquement s'il n'y a pas d'IBAN) : [{"societe": "nom de la société", "rib": {"banque": "nom de la banque", "code_banque": "...", "code_guichet": "...", "numero_compte": "...", "cle_rib": "..."}}]
""",
        "search": "Section du document qui décrit le groupement et les entreprises qui le composent.",
        "output_field": "rib_autres",
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
    "montant_ht": {
        "consigne": """MONTANT_HT  
     Définition : Montant du marché hors taxes (également hors TVA).  
     Indices : 
     - Rechercher les mentions "hors taxes", "HT", "sans TVA", "hors TVA" ou équivalent. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Cas particuliers :
        * Pour un marché en plusieurs lots (cf champ lot_concerne), ne renvoyer que le montant du lot concerné.
        * Pour un marché en plusieurs tranches, renvoyer la somme des montants de toutes les tranches.
     - Ne rien envoyer si aucun montant HT trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
        "search": "",
        "output_field": "montant_ht",
    },
    "montant_ttc": {
        "consigne": """MONTANT_TTC  
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
        "search": "",
        "output_field": "montant_ttc",
    },
    "duree": {
        "consigne": """DUREE
        Définition : Durée du marché totale exprimée en mois et extension possible.
        Indices :
        - Chercher dans le paragraphe indiquant la durée du marché ou le délai d'exécution des prestations.
        - Durée initiale : la durée du marché ferme (sans reconduction ou tranches optionnelles), en nombre de mois.
            * En l'absence de précisions sur la durée ferme, renvoyer duree_initiale: null
            * Exemple : une durée de 1 an, renvoyer 12.
            * Pour une durée entre des dates clés, par exemple "jusqu'à la réunion de conclusion 6 mois après le lancement" : renvoyer 6 mois.
                -> Attention : si ces dates clés sont insuffisamment documentées, renvoyer duree_initiale: null
        - Extension de durée possible : extenion maximale en nombre de mois.
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
        "output_field": "duree",
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
    "date_signature_mandataire": {
        "consigne": """DATE_SIGNATURE_MANDATAIRE
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
        "search": "",
        "output_field": "date_signature_mandataire",
    },
    "date_signature_administration": {
        "consigne": """DATE_SIGNATURE_ADMINISTRATION
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
        "search": "",
        "output_field": "date_signature_administration",
    },
    "date_notification": {
        "consigne": """DATE_NOTIFICATION
      Définition : Date de notification du marché aux mandataires. 
      Indices : 
      - Parfois en début du document, ou en toute fin de document.
      - Après la mention "Date de notification" ou "Date de début du marché".
      - S'il y a un doute sur la lecture de la date, prendre la date la plus proche postérieure à la signature par l'administration si disponible.
      - Peut aussi être la date d'un courrier de notification ou d'un mail en annexe du document.
      - S'il n'y a pas de date de notification explicite, ne rien renvoyer.
      - Attention à ne pas confondre la date de notification avec la date de signature.
     Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine  
""",
        "search": "",
        "output_field": "date_notification",
    },
    "conserve_avance": {
        "consigne": """CONSERVE_AVANCE
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
        "search": "",
        "output_field": "conserve_avance",
    },
    "montants_en_annexe": {
        "consigne": """MONTANTS_EN_ANNEXE  
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
        "search": "",
        "output_field": "montants_en_annexe",
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
        "consigne": """CODE_CPV — Code CPV (catégorie de dépense du marché).
        - Chercher "CPV", "Code CPV" ; format type 8 chiffres (optionnel + tiret + chiffre), éventuellement suivi de l'intitulé du code.
        - Ex. 72611000-6 - Fournitures
        Si plusieurs : priorité au CPV principal, sinon tous séparés par des ";" 
        Format : "XXXXXXXX-X Intitulé" ou "XXXXXXXX Intitulé". Sinon null.""",
        "search": "",
        "output_field": "code_cpv",
    },
    "montant_tva": {
        "consigne": """MONTANT_TVA
        Définition : Montant de la TVA.
        Indices :
        - Rechercher la mention de TVA ou de "taux de TVA". Le montant est souvent sous la forme d'un pourcentage.
        - Convertir le pourcentage en chiffre décimal entre 0 et 1.
        - Ne rien renvoyer si aucun montant de TVA trouvé.
        Format : en "0.XX" avec deux décimales (ex. 0.20 pour 20%).
        """,
        "search": "",
        "output_field": "montant_tva",
    },
    "mode_consultation": {
        "consigne": """MODE_CONSULTATION — Mode de passation du marché (procédure adaptée, appel d'offres, MAPA, etc.).
        Chercher dans intro, préambule ou visas. Extraire la citation exacte du document, sans reformuler. Sinon null.""",
        "search": "",
        "output_field": "mode_consultation",
    },
    "mode_reconduction": {
        "consigne": """MODE_RECONDUCTION — Reconduction du marché : expresse ou tacite ou null.
        - Sous la forme d'une case cochée ou explicitement mentionné dans le document.
        - Chercher "reconduction expresse", "reconduction tacite", "reconduit tacitement". Renvoyer "expresse" ou "tacite" si explicite.
        - Si aucune case cochée, et aucune mention renvoyer null.""",
        "search": "",
        "output_field": "mode_reconduction",
        "schema": {
            "type": "string",
            "enum": ["expresse", "tacite", "null"],
        },
    },
    "ligne_imputation_budgetaire": {
        "consigne": """LIGNE_IMPUTATION_BUDGETAIRE — Ligne budgétaire d’imputation de la dépense.
        Chercher "imputation budgétaire", "ligne budgétaire", "chapitre", "article". Format type : chiffres/lettres/tirets (ex. 0723-CDIE).
        Ne pas confondre avec référence de marché. Sinon null.""",
        "search": "",
        "output_field": "ligne_imputation_budgetaire",
    },
    "remise_catalogue":{
        "consigne": """REMISE_CATALOGUE — Remise dans le catalogue.
        - Remise sur le catalogue proposée par le fournisseur titulaire.
        - Sous la d'un pourcentage à renvoyer tel quel (ex. 10 pour cent -> renvoyer "10").
        - Si aucune case cochée, et aucune mention renvoyer null.""",
        "search": "",
        "output_field": "remise_catalogue",    
    }
}
