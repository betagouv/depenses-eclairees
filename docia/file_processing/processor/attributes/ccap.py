"""
Définitions des attributs à extraire pour les documents de type "ccap".
"""

CCAP_ATTRIBUTES = {
    "intro": {
        "consigne": """INTRODUCTION
    Ce paragraphe donne des précisions et des définitions sur le document à analyser. Le champ introduction n'appelle pas de réponse, renvoyer null.
    Définitions : 
    - LOT : l'acheteur peut décomposer un besoin en lots séparés, chacun constituant une marché à part entière lors de l'attribution. Autrement dit, un lot est une fraction du besoin globla, chaque lot est juridiquement équivalent à un marché autonome.
    - TRANCHE : un marché à tranches est un marché unique composé de plusieurs phases. La tranche ferme est celle pour laquelle l'acheteur s'engage contractuellement, les tranches optionnelles (ou conditionnelles) sont des parties supplementaires que l'acheteur peut faire exécuter plus tard.
    Attention : le terme de tranche peut parfois signifier autre chose. Il faut distinguer les tranches du marché (terme juridique) des tranches de prix ou de autre formulation non juridique.
""",
        "search": "",
        "output_field": "intro",
        "schema": {"type": "null"},
    },
    "objet_marche": {
        "consigne": """OBJET_MARCHE
    Définition : Formulation synthétique de l'objet du marché.
    Indices : 
    - L'objet du marché peut être dans le titre directement, ou plus généralement dans une section dédiée.
    - Identifier les formules comme "Objet du marché", "Le marché a pour objet", ou toute expression indiquant l'intitulé de la mission.
    Format : 
    - En bon Français
    - Attention, ne pas inclure le type de document dans l'objet : "Cahier des charges pour ..." enlever "Cahier des charges pour", ou "Marché pour ..." enlever "Marché pour".
    - Si l'objet de la commande est incompréhensible, proposer un objet simple qui reflète le contenu de la commande.
 
""",
        "search": "Section du document qui décrit l'objet du marché ou le contexte général de la consultation.",
        "output_field": "objet_marche",
    },
    "id_marche": {
        "consigne": """ID_MARCHE
    Définition : Identifiant unique du marché.
    Indices : 
    - Chercher dans le titre du document.
    - L'identifiant n'est pas standardisé entre les administrations, mais il contient généralement : 
        * L'année
        * Une désignation du pouvoir adjudicateur
        * Un numéro unique.
    Format : un identifiant unique de la consultation.
 
""",
        "search": "",
        "output_field": "id_marche",
    },
    "lots": {
        "consigne": """LOTS
     Définition : Liste des lots du marché (si le marché est alloti)
     Indices : 
     - Le marché est alloti si plusieurs lots sont décrits dans le CCAP : il faut que les lots soient explicitement citées avec la mention "Lot" et le titre de chaque lot.
     - Pour chaque lot :
        * Identifier le numéro du lot
        * Identifier le titre du lot
        * Si dans le texte, il n'est pas écrit pour chaque lot "Lot ...", alors ce n'est pas un lot.
     - Il peut y avoir des mentions à des lots dans le CCAP par erreur de rédaction, sans qu'il y ait véritablement de lots pour autant.
     - Ne pas inclure les tranches dans la liste des lots. Les tranches sont des sous-parts d'un lot, elles ne donnent pas lieu à des sous-marchés.
     Format : une liste de json [{'numero_lot': numéro du lot, 'titre_lot': l'intitulé du lot }, {...}]
""",
        "search": "",
        "output_field": "lots",
        "schema": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {"numero_lot": {"type": "integer"}, "titre_lot": {"type": "string"}},
                "required": ["numero_lot", "titre_lot"],
            },
        },
    },
    "forme_marche": {
        "consigne": """FORME_MARCHE
        Définition : Identifier la forme de passation du marché.
        Indices :
        - Rechercher dans les sections de la forme du marché et dans celle définissant les lots.
        - SI le marché comporte des lots (le champ LOTS n'est pas []), renvoyer : structure = "allotie", tranches = null, forme_prix = null, attributaires = null
        - OU ALORS si le marché ne comprend pas de lots (LOTS = [])
            (1) Identifier la structure d'exécution marché :
                * Si le marché n'a pas de lots et donne lieu à des marchés subséquents (le document précise par exemple "pour les marchés subséquents, ..."), structure = "à marchés subséquents"
                * Si les termes "marchés subséquents" ne sont jamais mentionnés dans l'ensemble du document, structure = "simple".
                * L'allotissement du marché global prime ici sur les marchés subséquents : si le marché est alloti, structure = "allotie".
                * Sinon, structure = "simple"
            (2) Identifier les tranches du marché :
                * Si le marché comporte des tranches (cf définition dans l'introduction), renvoyer le nombre de tranches explicitement listées pour le marché (tranches fermes inclues).
                * Si le marché n'a qu'une tranche ferme, renvoyer tranches = 1.
                * Sinon, tranches = null.
            (3) Identifier la forme des prix du marché : "unitaires", "forfaitaires" ou "mixtes". Regarder dans la section des prix et des documents annexes au ccap.
                * Prix unitaires : les prix sont unitaires si le document précise que les prix sont unitaires, ou qu'il cite un document de bordereaux de prix unitaires (ou BPU).
                * Prix forfaitaires : les prix sont forfaitaires si le document précise que les prix sont forfaitaires, ou qu'il cite un document de décomposition (globale) des prix forfaitaires (ou DGPF ou DPGF).
                * Prix mixtes : les prix sont mixtes si le document précise que les prix sont mixtes, ou qu'ils sont à la fois unitaires et forfaitaires.
                * Par défaut, la forme des prix est forfaitaire.
            (4) Identifier le nombre d'attibutaires du marché :
                * Si le marché est mono-attributaire, renvoyer 1.
                * Si le marché est multi-attributaire, chercher le nombre d'attibutaires maximum.
                * Sinon attributaires = null
        Format : un json {'structure': ..., 'tranches': ..., 'forme_prix': ..., 'attributaires': ...}.
   """,
        "search": "",
        "output_field": "forme_marche",
        "schema": {
            "type": ["object", "null"],
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "structure": {"type": "string", "enum": ["allotie"]},
                        "tranches": {"type": "null"},
                        "forme_prix": {"type": "null"},
                        "attributaires": {"type": "null"},
                    },
                    "required": ["structure", "tranches", "forme_prix", "attributaires"],
                },
                {
                    "type": "object",
                    "properties": {
                        "structure": {"type": "string", "enum": ["simple", "à marchés subséquents"]},
                        "tranches": {"type": ["integer", "null"]},
                        "forme_prix": {"type": "string", "enum": ["unitaires", "forfaitaires", "mixtes"]},
                        "attributaires": {"type": ["integer", "null"]},
                    },
                    "required": ["structure", "tranches", "forme_prix", "attributaires"],
                },
            ],
        },
    },
    "forme_marche_lots": {
        "consigne": """FORME_MARCHE_LOTS
        Définition : Identifier la forme de passation des lots du marché (seulement si le marché est alloti).
        Indices :
        - Rechercher dans les sections de la forme du marché et dans celle définissant les lots (cf LOTS ci-dessus). Si le marché ne comprend pas de lots, renvoyer [].
        - Si la structure et les formes des lots ne sont pas spécifiquement définies, c'est que leurs structures et formes sont identiques à celles du marché.
        - Pour chaque lot, identifier le numéro du lot.
        - Pour chaque lot, identifier la structure de passation du lot : 
            * Si l'ensemble du marché s'exécute par marchés subséquents, ALORS pour chaque lot structure = "à marchés subséquents".
            * Si le lot s'exécute par conclusion de marchés subséquents, structure = "à marchés subséquents".
            * Si les termes "marchés subséquents" ne sont jamais mentionnés dans l'ensemble du document, structure = "simple".
            * Sinon, structure = "simple"
        - Pour chaque lot, identifier les tranches du lot, s'il y en a :
            * Si le lot comporte des tranches (cf définition dans l'introduction), renvoyer le nombre de tranches explicitement listées pour le lot (tranches fermes inclues).
            * S'il y a plusieurs tranches optionnelles ou conditionnelles, compter le nombre total de tranches disponibles pour le lot.
            * Si le lot n'a qu'une tranche ferme, renvoyer tranches = 1.
            * Sinon, tranches = null.
        - Pour chaque lot, identifier la forme des prix du lot : "mixtes", "unitaires", ou "forfaitaires". Regarder dans la section des prix et des documents annexes au ccap.
            * Prix mixtes : si les prestations de ce lot sont d'une part à prix forfaitaires et d'autre part à prix unitaires (les prix des prestations du lot évoquées à plusieurs endroits). forme_prix = "mixtes".
            * Prix unitaires : les prix sont unitaires si le document précise que les prix sont unitaires, ou qu'il cite un document de bordereaux de prix unitaires (ou BPU). forme_prix = "unitaires".
            * Prix forfaitaires : les prix sont forfaitaires si le document précise que les prix sont forfaitaires, ou qu'il cite un document de décomposition (globale) des prix forfaitaires (ou DGPF ou DPGF). forme_prix = "forfaitaires".
            * ATTENTION : La qualification "mixtes" est prioritaire : dès lors qu’un même lot comporte à la fois des prestations à prix unitaires et à prix forfaitaires, la forme des prix du lot DOIT être "mixtes", même si les documents BPU ou DPGF sont cités.
        - Pour chaque lot, identifier le nombre d'attibutaires du lot :
            * Si le lot est mono-attributaire ou qu'il n'est pas fait mention du nombre d'attributaires, renvoyer 1.
            * Si le lot est multi-attributaire, chercher le nombre d'attibutaires maximum.
        Format : une liste de json [{'numero_lot': numéro du lot, 'structure': structure, 'tranches': nombre de tranches, 'forme_prix': forme_prix, 'attributaires': nombre d'attibutaires}, {...}]
   """,
        "search": "",
        "output_field": "forme_marche_lots",
        "schema": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "numero_lot": {"type": "integer"},
                    "structure": {"type": "string", "enum": ["simple", "à marchés subséquents"]},
                    "tranches": {"type": ["integer", "null"]},
                    "forme_prix": {"type": "string", "enum": ["mixtes", "unitaires", "forfaitaires"]},
                    "attributaires": {"type": ["integer", "null"]},
                },
                "required": ["numero_lot", "structure", "tranches", "forme_prix", "attributaires"],
            },
        },
    },
    # Ajouter si durée préciser dans l'acte d'engagement, renvoyer None à chaque valeur.
    "duree_marche": {
        "consigne": """DUREE_MARCHE
        Définition : Durée du marché totale exprimée en mois et extension possible.
        Indices :
        - Chercher dans le paragraphe indiquant la durée du marché ou le délai d'exécution des prestations.
        - Durée initiale : la durée du marché ferme (sans reconduction ou tranches optionnelles), en nombre de mois.
            * En l'absence de précisions sur la durée ferme, renvoyer ''
            * Exemple : une durée de 1 an, renvoyer 12.
            * Pour une durée entre des dates clés, par exemple "jusqu'à la réunion de conclusion 6 mois après le lancement" : renvoyer 6 mois.
                -> Attention : si ces dates clés sont insuffisamment documentées, renvoyer ''
        - Extension de durée possible : extenion maximale en nombre de mois.
            * En l'absence d'informations claires, renvoyer ''
            * Si des reconductions sont précisées (ne pas confondre avec des tranches optionnelles qui sont gérées ci-dessous) :
                1. duree_reconduction : Trouver la durée d'une reconduction (en nombre de mois). Si l'information n'est pas précisée, renvoyer ''.
                2. nb_reconductions : Trouver le nombre de reconductions possibles. Si l'information n'est pas précisée, renvoyer ''.
            * Si des tranches optionnelles sont précisées : renvoyer la durée de l'ensemble des tranches optionnelles.
                1. delai_tranche_optionnelle : Trouver la durée de l'ensemble des tranches optionnelles.
                    Exemple : 2 tranches optionnelles de 8 mois, renvoyer 8 + 8 = 16.
        Format : un json sous format suivant {"duree_initiale": "nombre entier de mois", "duree_reconduction": "nombre entier de mois", "nb_reconductions": "nombre entier de reconductions possibles", "delai_tranche_optionnelle": "nombre entier de mois"}
    """,
        "search": "Section du document qui décrit la durée du marché ou le délai d'exécution des prestations.",
        "output_field": "duree_marche",
        "schema": {
            "type": ["object", "null"],
            "properties": {
                "duree_initiale": {"type": "integer"},
                "duree_reconduction": {"type": "integer"},
                "nb_reconductions": {"type": "integer"},
                "delai_tranche_optionnelle": {"type": "integer"},
            },
            "required": ["duree_initiale", "duree_reconduction", "nb_reconductions", "delai_tranche_optionnelle"],
        },
    },
    "duree_lots": {
        "consigne": """DUREE_LOTS
     Définition : Durée de chaque lot du marché exprimée en mois.
     Indices : 
     - S'il n'y pas de lots, renvoyer []
     - Dans la section spécifique de la durée du marché.
     - Si la durée des lots est la même que celle du marché, renvoyer la valeur 'identique à la durée du marché' pour chacun des lots.
     - Si des spécifités sont précisées pour la durée des lots, renvoyer la durée de chaque lot sous format d'un json : 
        * {"duree_initiale": "nombre entier de mois", "duree_reconduction": "nombre entier de mois", "nb_reconductions": "nombre entier de reconductions possibles", "delai_tranche_optionnelle": "nombre entier de mois"}
     - Si la durée sera précisée ultérieurement (dans l'acte d'engagement par exemple), renvoyer []
     Format : une liste de json [{"numero_lot": numéro du lot, "duree_lot": "string" ou objet json}, ...].
""",
        "search": "",
        "output_field": "duree_lots",
        "schema": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "numero_lot": {"type": "integer"},
                    "duree_lot": {
                        "oneOf": [
                            {"type": "string", "enum": ["identique à la durée du marché"]},
                            {
                                "type": "object",
                                "properties": {
                                    "duree_initiale": {"type": "integer"},
                                    "duree_reconduction": {"type": "integer"},
                                    "nb_reconductions": {"type": "integer"},
                                    "delai_tranche_optionnelle": {"type": "integer"},
                                },
                                "required": [
                                    "duree_initiale",
                                    "duree_reconduction",
                                    "nb_reconductions",
                                    "delai_tranche_optionnelle",
                                ],
                            },
                        ]
                    },
                },
                "required": ["numero_lot", "duree_lot"],
            },
        },
    },
    # Ajout si sans montant maximum explicite, renvoyer None
    "montant_ht": {
        "consigne": """MONTANT_HT
      Définition : Montant maximum hors taxes du marché pour un marché non alloti.
      Indices :
     - Dans la section spécifique des montants du marché, ou dans la forme du marché.
     - Si le marché est alloti, ne rien renvoyer.
     - montant_ht_maximum : renvoyer le montant maximum hors taxes au format "XXXX.XX" (2 décimales, sans espaces séparateurs de milliers)
     - type_montant : renvoyer "annuel" si le montant est annuel, "total" si le montant est global. Si plusieurs possibilités, renovyer le montant hors taxes annuel.
     - S'il n'y a pas d'informations disponibles sur le montant maximum hors taxes, renvoyer null.
     Format : un json {"montant_ht_maximum": "XXXX.XX", "type_montant": "annuel" ou "total"}.
""",
        "search": "",
        "output_field": "montant_ht",
        "schema": {
            "type": ["object", "null"],
            "properties": {
                "montant_ht_maximum": {"type": "string"},
                "type_montant": {"type": "string", "enum": ["annuel", "total"]},
            },
            "required": ["montant_ht_maximum", "type_montant"],
        },
    },
    "montant_ht_lots": {
        "consigne": """MONTANT_HT_LOTS
     Définition : Montant hors taxes maximum de chaque lot du marché.
     Indices : 
     - Dans la section spécifique des montants maximums hors taxes des lots du marché, ou dans la forme du marché.
     - Pour chaque lot, trouver le montant maximum hors taxe.
     - Exceptions :
        * Si le marché n'est pas alloti, renvoyer []
        * Si le montant des lots est précisé ultérieurement (dans l'acte d'engagement par exemple), ou s'il n'y pas d'informations sur les montants maximums hors taxes, renvoyer []
     - Pour chaque montant hors taxes, indiquer si le montant maximum est annuel ou pour toute la durée du marché.
     Format : une liste de json au format suivant [{"numero_lot": le numéro du lot, 'montant_ht_maximum': le montant hors taxes maximum du lot en "XXXX.XX" (sans séparateur de milliers, avec 2 décimales) sans unité monétaire, 'type_montant': 'annuel' ou 'total'}, {...}]
""",
        "search": "",
        "output_field": "montant_ht_lots",
        "schema": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "numero_lot": {"type": "integer"},
                    "montant_ht_maximum": {"type": "string"},
                    "type_montant": {"type": "string", "enum": ["annuel", "total"]},
                },
                "required": ["numero_lot", "montant_ht_maximum", "type_montant"],
            },
        },
    },
    "ccag": {
        "consigne": """CCAG
     Définition : Le CCAG en vigueur pour ce marché.
     Indices : 
     - Dans le corps du document, ou en dernier paragraphe dans les dérogations au CCAG.
     - Souvent cité par la forme "CCAG-XXXX". Le XXXX est l'acronyme du CCAG de référence : renvoyer XXXX.
     - Si le CCAG spécifique est cité en toutes lettres, renvoyer seulement l'acronyme : Exemple : "CCAG de prestations intellectuelles" renvoyer "PI".
     - Si un CCAG est mentionné, mais sans préciser lequel (acronyme ou en toutes lettres), renvoyer null.
     - Si aucun CCAG n'est mentionné, renvoyer null.
     Format : un acronyme de quelques lettres ou null.
""",
        "search": "",
        "output_field": "ccag",
    },
    "condition_avance": {
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
   Format : {'condition_declenchement':"", 'montant_avance':XX%, 'montant_reference':"", 'remboursement':XX%-XX%}
""",
        "search": "avance accordée titulaire montant initial durée exécution remboursement précompte",
        "output_field": "condition_avance_ccap",
        "schema": {
            "type": "object",
            "properties": {
                "condition_declenchement": {"type": "string"},
                "montant_avance": {"type": "string"},
                "montant_reference": {"type": "string"},
                "remboursement": {"type": "string"},
            },
            "required": ["condition_declenchement", "montant_avance", "montant_reference", "remboursement"],
        },
    },
    "formule_revision_prix": {
        "consigne": """FORMULE_REVISION_PRIX
    Définition : Détail de la formule mathématique permettant de réviser les prix du marché.
    Indices :
    - Rechercher la clause "Formule de révision" ou "Coefficient de révision".
    - La formule exprime généralement un coefficient de révision (noté 'C', 'K', ou 'Cn') qui s'applique au prix initial (P0).
    A. Identifier :
        1. La partie fixe (ou "marge d'amortissement") : c'est le chiffre constant qui n'est pas multiplié par un indice (ex: 0.15).
        2. Les termes variables : chaque terme est composé d'un poids (ex: 0.85) et d'un ratio d'indices (Indice nouveau / Indice de référence).
    - Attention : La somme de la partie fixe et des poids des termes variables doit normalement être égale à 1 (ou 100%).
    Exemple de formule : "C = 0.30 + 0.20 * I_1N / I_10N + 0.50 * I_2N / I_20N".
    Ici, le coefficient C a trois facteurs :
        * partie fixe, de poids 0.30.
        * facteur évolution de l'indice 1 (I_1N / I_10N), de poids 0.20. 
        * facteur évolution de l'indice 2 (I_2N / I_20N), de poids 0.50. 
    B. TEMPORALITÉ ET DÉFINITIONS - Pour chaque indice de la formule, extraire précisément :
        1. Nom et Source : Le nom de l'indice (ex: Syntec, BT01) et sa source (ex: INSEE).
        2. Indice de Référence (le dénominateur, ex: I0 ou S0) : 
        - Extraire la règle de date/mois de base (ex: "valeur du 3ème mois précédant la date de notification").
        3. Indice Nouveau (le numérateur, ex: In ou Sn) : 
       - Extraire la règle de calcul de la nouvelle valeur (ex: "dernier indice publié au mois de la prestation" ou "valeur connue avec un décalage de 3 mois").
        Format : Renvoyer un objet structuré détaillant la partie fixe et la liste des termes_variables avec leurs poids respectifs.
        """,
        "search": "formule de révision des prix coefficient C K partie fixe terme fixe pondération",
        "output_field": "formule_revision_prix",
        "schema": {
            "type": "object",
            "properties": {
                "formule_brute": {"type": ["string", "null"]},
                "partie_fixe": {"type": ["number", "null"]},
                "termes_variables": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "object",
                        "properties": {
                            "poids": {"type": ["number", "null"]},
                            "nom_indice": {"type": ["string", "null"]},
                            "source_indice": {"type": ["string", "null"]},
                            "symbole_indice_reference": {"type": ["string", "null"]},
                            "regle_temporelle_indice_reference": {"type": ["string", "null"]},
                            "symbole_indice_nouveau": {"type": ["string", "null"]},
                            "regle_temporelle_indice_nouveau": {"type": ["string", "null"]}
                        },
                        "required": ["poids", "nom_indice", "source_indice", "symbole_indice_reference", "regle_temporelle_indice_reference", "symbole_indice_nouveau", "regle_temporelle_indice_nouveau"]
                    }
                }
            },
            "required": ["formule_brute", "partie_fixe", "termes_variables"]
        }
    },
    "index_reference": {
        "consigne": """INDEX_REFERENCE
    Définition : Index de référence utilisé pour la révision des prix.
    Indices :
    - Dans une section spécifique de l'index de référence.
    Format : le nom de l'index de référence.
""",
        "search": "",
        "output_field": "index_reference"
    },
    "revision_prix": {
        "consigne": """REVISION_PRIX
     Définition : Evolution possible des prix du marché.
     Indices :
     - Dans la section spécifique aux prix.
     - Les prix peuvent être :
        * Révisables : les prix sont révisables par une formule, ou bien par un nouveau document financier (BPU, catalogue de prix).
        * Fermes : les prix sont fermes, c'est à dire qu'ils ne peuvent pas être révisés. Formules "fermes" ou "définitifs".
     - Si aucun paragraphe sur la révision des prix n'est présent et aucune mention de prix fermes ou révisables, renvoyer null.
""",
        "search": "",
        "output_field": "revision_prix",
        "schema": {"type": ["string", "null"], "enum": ["fermes", "révisables", None]},
    },
    "mode_consultation": {
        "consigne": """MODE_CONSULTATION
    Définition : Identification de la procédure de passation.
    - Si mention de L.2123-1 ou R.2123-1 -> type_procedure : "Procédure adaptée (MAPA)"
    - Si mention de L.2124-2, R.2161-2 (Appel d'offres) ou L.2124-3 (Négociation) -> type_procedure : "Procédure formalisée".
    - Si procédure formalisée (L.2124-2, R.2161-2, etc.), préciser la forme :
        * "Procédure formalisée - Appel d'offres ouvert"
        * "Procédure formalisée - Appel d'offres restreint"
        * "Procédure formalisée - Avec négociation"
        * "Procédure formalisée - Dialogue compétitif"
    Note : Si le texte est ambigu, privilégier l'article de loi cité pour déterminer la catégorie.
""",
        "search": "procédure passation consultation appel d'offres MAPA procédure adaptée article L.2123-1 R.2122-8 formalisée",
        "output_field": "mode_consultation",
        "schema": {
            "type": ["object", "null"],
            "properties": {
                "type_procedure": {
                    "type": ["string", "null"],
                    "enum": [
                        "Procédure adaptée (MAPA)",
                        "Procédure formalisée - Appel d'offres ouvert",
                        "Procédure formalisée - Appel d'offres restreint",
                        "Procédure formalisée - Avec négociation",
                        "Procédure formalisée - Dialogue compétitif",
                        "Sans publicité ni mise en concurrence"
                    ]
                }
            }
        }
    },
    "regle_attribution_bc": {
        "consigne": """REGLE_ATTRIBUTION_BC
    Définition : Méthode de choix du titulaire pour l'émission des bons de commande (concerne les accords-cadres multi-attributaires).
    Indices : 
    - Dans la section exécution des bons de commande ou règles d'attribution.
    - Pour un marché multi-attributaire, chercher si les bons de commande sont attribués :
    * "En cascade" : le texte cite le terme de "cascade", avec un premier titulaire qui reçoit toutes les commandes sauf s'il fait défaut.
    * "A tour de rôle" : les bons de commandes sont répartis "par tour de rôle", ou par "rotation" des titulaires.
    * "Avec remise en concurrence" : le texte parle de remise en concurrence et de marchés subséquents.
    * "Avec minimums d'attribution" (suivis des montants minimums si disponibles) :
    le marché est multi-attributaire à bons de commande mais ne cite aucune des règles ci-dessus.
    Dans ce cas, chercher les parts minimales de commande attribuées par titulaire.
    Ex : 1er : 10%, 2e : 10%, 3e : 5% -> renvoyer "Avec minimums d'attribtion 10%, 10%, 5%".
    - Si le marché est mono-attributaire, ne rien renvoyer.
    Format : string parmi "En cascade", "A tour de rôle", "Avec remise en concurrence", "Avec minimums d'attribution".
""",
        "search": "attribution bons de commande cascade tour de rôle remise en concurrence",
        "output_field": "regle_attribution_bc",
    },
    "type_reconduction": {
        "consigne": """TYPE_RECONDUCTION
    Définition : Modalité de reconduction du marché.
    Indices :
    - Dans le paragraphe sur la durée du marché, ou concernant la reconduction du marché.
    - Si le marché est reconductible, chercher la modalité de reconduction parmi :
    * "Tacite" : le marché se reconduit sans besoin d'une expression de reconduction.
    * "Expresse" : le marché se reconduit par une expression de reconduction.
    * "Null" : si le marché n'est pas reconductible, ou si la modalité de reconduction n'est pas précisée.
    Format : "tacite" ou "expresse" ou null.
""",
        "search": "reconduction tacite expresse",
        "output_field": "type_reconduction",
        "schema": {"type": ["string", "null"], "enum": ["tacite", "expresse", None]},
    },
    "debut_execution": {
        "consigne": """DEBUT_EXECUTION
    Définition : Point de départ de la durée du marché ou des prestations.
    Indices : 
    - Souvent : "à la date de notification", "à compter de l'ordre de service (OS)", ou une date fixe.
    Format : Texte court (ex: "date de notification" ou "1er janvier 2024").
""",
        "search": "début exécution prise d'effet notification ordre de service",
        "output_field": "debut_execution",
    },
    "avance": {
        "consigne": """AVANCE
    Définition : Paramètres de l'avance selon les clauses du marché et le Code de la Commande Publique (CCP).
    1. TAUX (Standard & PME) :
       - Extraire le taux écrit, sous forme d'un pourcentage (ex: 5%).
       - Extraire le taux spécifique au PME, ou valeur par défaut.
       - Si le document ne donne pas plus de précision, les taux par défaut s'appliquent :
         * Taux Standard (si aucune précision, par défaut) : 5%.
         * Taux PME (si aucune précision, par défaut) : 30%.
    2. DÉCLENCHEMENT :
       - L'avance est obligatoire si : Montant > 50 000 € HT ET Durée > 2 mois.
       - Si ces seuils ne sont pas mentionnés mais que le document parle d'avance, 
       considérer ces seuils comme acquis par défaut.
    3. ASSIETTE & CALCUL (Art. R2191-7) :
       - Base de calcul : Montant initial TTC du marché, de la tranche, du bon de commande, ...
       - Unité fiscale : Par défaut "TTC" (sauf mention contraire).
       - Règle de durée : coefficient de prorata temporis (12 * Montant TTC / Durée en mois). Renvoyer "True" sauf mention contraire.
    4. REMBOURSEMENT (Art. R2191-11) :
       - Si le marché est silencieux ou renvoie au Code :
         * Si Taux Avance <= 30% : Début de remboursement à 65% d'exécution, Fin à 80%.
         * Si Taux Avance > 30% : Début dès la 1ère demande de paiement (0%), Fin à 80%.
       - Si le document précise d'autres seuils, extraire les valeurs du document.
    Format : Renvoyer un objet JSON. Pour les champs déduits du Code (et non écrits en clair), ajouter la mention "(par défaut CCP)".
""",
        "search": "avance taux PME montant 50000 durée 2 mois assiette HT TTC remboursement précompte 65% 80% prorata 12 mois",
        "output_field": "avance",
        "schema": {
            "type": ["object", "null"],
            "properties": {
                "taux": {
                    "type": ["object", "null"],
                    "properties": {
                        "standard": {"type": ["string", "null"]},
                        "pme": {"type": ["string", "null"]}
                    }
                },
                "declenchement": {
                    "type": ["object", "null"],
                    "properties": {
                        "seuil_montant_ht": {"type": ["number", "null"]},
                        "seuil_duree_mois": {"type": ["number", "null"]}
                    }
                },
                "assiette": {
                    "type": ["object", "null"],
                    "properties": {
                        "unite_fiscale": {"type": ["string", "null"], "enum": ["HT", "TTC"]},
                        "base_calcul": {"type": ["string", "null"]},
                        "regle_prorata_12_mois": {"type": ["boolean", "null"]}
                    },
                    "required": ["base_calcul"]
                },
                "remboursement": {
                    "type": ["object", "null"],
                    "properties": {
                        "pourcentage_debut": {"type": ["string", "null"]},
                        "pourcentage_fin": {"type": ["string", "null"]}
                    }
                }
            },
            "required": ["taux", "declenchement", "assiette", "remboursement"]
        }
    },
    "retenue_garantie": {
        "consigne": """RETENUE_GARANTIE
    Définition : Somme retenue sur les paiements pour garantir la bonne exécution.
    Indices : 
    - Chercher un pourcentage (souvent 5%) prélevé sur les acomptes.
    - Mentionner si elle peut être remplacée par une caution.
    Format : Paragraphe libre résumant les conditions. Si absent, renvoyer null.
""",
        "search": "retenue de garantie caution garantie à première demande",
        "output_field": "retenue_garantie",
    },
    "mois_zero_revision": {
        "consigne": """MOIS_ZERO_REVISION
    Définition : Mois de référence de l'indice pour la révision des prix.
    Indices : 
    - Souvent appelé "M0" ou "mois d'établissement des prix".
    - Peut être une date précise ou une description relative (ex: "mois de la notification").
    Format : "01/MM/AAAA" ou texte descriptif.
""",
        "search": "mois zéro M0 établissement des prix",
        "output_field": "mois_zero_revision",
    },
    "clause_sauvegarde_revision": {
        "consigne": """CLAUSE_SAUVEGARDE_REVISION
    Définition : Limite ou condition d'annulation de la révision des prix.
    Indices : 
    - Chercher des seuils de variation (ex: "+/- 2%").
    - Identifier la conséquence : blocage du prix ou annulation de la révision.
    Format : JSON {"seuil": "XX%", "consequence": "texte"}.
""",
        "search": "clause de sauvegarde révision blocage seuil",
        "output_field": "clause_sauvegarde_revision",
        "schema": {
            "type": "object",
            "properties": {
                "seuil": {"type": "string"},
                "consequence": {"type": "string"},
            },
        },
    },
    "delai_execution_entite": {
        "consigne": """DELAI EXECUTION ENTITE
    Définition : Délai impart pour émettre et cloturer des bons de commande (BC) et des marchés subséquents (MS).
    Indices : 
    - Dans la section exécution des bons de commande ou des marchés subséquents s'il y en a.
    - Chercher le délai pour émettre et cloturé des bons de commande (BC) et des marchés subséquents (MS).
    Format : JSON {"type": "BC" ou "MS", "delai": "texte"}.
""",
        "search": "délai exécution bon de commande marché subséquent émettre cloturer",
        "output_field": "delai_execution_entite",
        "schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["BC", "MS"]},
                "delai": {"type": "string"},
            },
        },
    },
    "penalites": {
        "consigne": """PENALITES
    Définition : Sanctions financières en cas de retard ou de mauvaise exécution.
    Indices : 
    - Lister chaque type de pénalité séparément.
    - Pour chaque pénalité, trouver :
        * La condition de la pénalité
        * Le montant de la pénalité : en €, en %, en quantité simple.
        * L'unité de la pénalité : par jour de retard, par quantité de quelque chose, etc.
    - Si une pénalité n'est pas proportionnelle (montant variable par paliers), créer plusieurs entrées forfaitaires.
    Format : Liste de JSON [{"condition": "ex: retard livraison", "montant": "valeur numérique", "unite": "ex: par jour de retard"}].
""",
        "search": "pénalités retard inexécution déduction",
        "output_field": "penalites",
        "schema": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "condition": {"type": "string"},
                    "montant": {"type": "string"},
                    "unite": {"type": "string"},
                },
            },
        },
    },
    "code_cpv": {
        "consigne": """CODE_CPV
    Définition : Nomenclature européenne pour les marchés publics.
    Indices : 
    - Un code CPV est de la forme : 
        * 8 chiffres (ex: 72000000-5) suivi d'un indice de classement (ex: -5)
        * Suivi éventuellement de l'intitulé du code (ex: "Fournitures")
    - Renvoyer la liste des codes CPV présents dans le document.
    - Selon que les codes CPV sont décomposés en plusieurs lots ou non :
        * sous la forme d'une liste simple si les codes ne sont pas ventilés par lots
        * Sous une liste de dictionnaires si les codes sont ventilés par lots.
    - Si absent du document, renvoyer null (ne pas essayer de le deviner).
    Format : une liste de codes CPV ou null.
""",
        "search": "CPV nomenclature",
        "output_field": "code_cpv",
        "schema": {
            "type": ["array", "null"],
            "items": {
                "oneOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "properties": {
                            "numero_lot": {"type": "integer"},
                            "codes_cpv": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["numero_lot", "codes_cpv"],
                    },
                ],
            },
        },
    },
}
