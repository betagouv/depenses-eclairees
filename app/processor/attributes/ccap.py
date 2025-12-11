"""
Définitions des attributs à extraire pour les documents de type "ccap".
"""

CCAP_ATTRIBUTES = {
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
        "output_field": "objet_marche_ccap"
    },

    "lots": {
        "consigne": """LOTS
     Définition : Liste des lots du marché (si le marché est alloti)
     Indices : 
     - Rechercher les lots du marché dans la section de l'alotissement.
     - Si une décomposition en lots est mentionnée ailleurs dans le document, alors renvoyer la liste des lots avec les informations trouvées.
     Format : une liste de json [{'numero_lot': numéro du lot, 'titre_lot': l'intitulé du lot }, {...}]
""",
        "search": "",
        "output_field": "lots",
        "schema":
        {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numero_lot": {"type": "integer"},
                    "titre_lot": {"type": "string"}
                },
                "required": ["numero_lot", "titre_lot"]
            }
        }
    },

    "forme_marche": {
        "consigne": """FORME_MARCHE
     Définition : La forme de passation des commandes, ou des marchés subséquents de ce marché.
     Indices : 
     - Rechercher la forme du marché dans un paragraphe sur la forme du marché ou sur la passation des commandes ou sur la passation de marchés subséquents.
     - Si le marché est désigné comme un accord-cadre, il donne souvent lieu à des marchés subséquents (directement ou dans certains de ses lots).
     - (1) Si le marche ne comprend ni lot, ni marchés subséquents, alors :
        * Structure = 'simple'
        * Forme = 'à bons de commande' ou 'à tranches' ou 'forfaitaire'
     - (2) Si le marché comprend des lots :
        * Structure = 'allotie'
        * Forme est une liste de json [{'numero_lot': numéro de lot, 'forme': {'structure': ..., 'forme': ...}}]
        * Appliquer le raisonnement pour chaque lot comme s'il était un nouveau marché en lui-même.
            > Par exemple, le marché comporte 2 lots, un à bons de commande, et l'autre à marchés subséquents. On traite chaque lot comme s'il était un nouveau marché en lui-même.
                > Le lot 1 est à bons de commande, on applique la consi1) : {'structure': 'simple', 'forme': 'à bons de commande'}
                > Le lot 2 est à marchés subséquents, on applique la consigne (3) : {'structure': 'à marchés subséquents', 'forme': {'structure': 'simple', 'forme': 'à bons de commande' ou 'à tranches' ou 'forfaitaire'}}
        * ATTENTION : S'il est mentionné "des marchés subséquents pour les lots ...", c'est que les lots sont "à marchés subséquents" (même si ce n'est pas explicitement mentionné dans la forme du marché).
     - (3) Si le marché donne lieu à des marchés subséquents directement (et non que ses lots donnent lieu à des marchés subséquents) :
        * Structure = 'à marchés subséquents'
        * Forme = un json {'structure': 'simple' 'forme': 'à bons de commande' ou 'à tranches' ou 'forfaitaire'} selon la forme des marchés subséquents.
     Format : un json {'structure': ..., 'forme': ...}. La forme est elle-même un json.
   """,
        "search": "",
        "output_field": "forme_marche",
        "schema":
        {
        "type": "object",
        "oneOf": [
            {
                "type": "object",
                "properties": {
                        "structure": {
                        "type": "string",
                        "enum": ["simple"]
                    },
                    "forme": {
                        "type": "string",
                        "enum": ["à bons de commande", "à tranches", "forfaitaire"]
                    }
                },
                "required": ["structure", "forme"]
            },
            {
                "type": "object",
                "properties": {
                    "structure": {
                        "type": "string",
                        "enum": ["allotie"]
                    },
                    "forme": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                            "numero_lot": {
                                "type": "integer"
                            },
                            "forme": {
                                "type": "object",
                                "oneOf": [
                                    {
                                        "type": "object",
                                        "properties": {
                                            "structure": {
                                                "type": "string",
                                                "enum": ["simple"]
                                            },
                                            "forme": {
                                                "type": "string",
                                                "enum": ["à bons de commande", "à tranches", "forfaitaire"]
                                            }
                                        },
                                        "required": ["structure", "forme"]
                                    },
                                    {
                                        "type": "object",
                                        "properties": {
                                            "structure": {
                                                "type": "string",
                                                "enum": ["à marchés subséquents"]
                                            },
                                            "forme": {
                                                "type": "object",
                                                "properties": {
                                                    "structure": {
                                                        "type": "string",
                                                        "enum": ["simple"]
                                                    },
                                                    "forme": {
                                                        "type": "string",
                                                        "enum": ["à bons de commande", "à tranches", "forfaitaire"]
                                                    }
                                                },
                                                "required": ["structure", "forme"]
                                            }
                                        },
                                        "required": ["structure", "forme"]
                                    }
                                ]
                            }
                            },
                            "required": ["numero_lot", "forme"]
                        }
                    }
                },
                "required": ["structure", "forme"]
            },
            {
                "type": "object",
                "properties": {
                    "structure": {
                    "type": "string",
                    "enum": ["à marchés subséquents"]
                    },
                    "forme": {
                    "type": "object",
                    "properties": {
                        "structure": {
                        "type": "string",
                        "enum": ["simple"]
                        },
                        "forme": {
                        "type": "string",
                        "enum": ["à bons de commande", "à tranches", "forfaitaire"]
                        }
                    },
                    "required": ["structure", "forme"]
                    }
                },
                "required": ["structure", "forme"]
            }
        ]
        }
    },

    "duree": {
        "consigne": """DUREE
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
        "output_field": "duree",
        "schema":
        {
            "type": "object",
            "properties": {
                "duree_initiale": {"type": "integer"},
                "duree_reconduction": {"type": "integer"},
                "nb_reconductions": {"type": "integer"},
                "delai_tranche_optionnelle": {"type": "integer"}
            },
            "required": ["duree_initiale", "duree_reconduction", "nb_reconductions", "delai_tranche_optionnelle"]
        }
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
     Format : une liste de json [{"numero_lot": numéro du lot, "duree_lot": "string" ou objet json}, ...].
""",
        "search": "",
        "output_field": "duree_lots",
        "schema":
        {
            "type": "array",
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
                                    "delai_tranche_optionnelle": {"type": "integer"}
                                },
                                "required": ["duree_initiale", "duree_reconduction", "nb_reconductions", "delai_tranche_optionnelle"]
                            }
                        ]
                    }
                },
                "required": ["numero_lot", "duree_lot"]
            }
        }
    },

    "montant_ht": {
        "consigne": """MONTANT_HT
      Définition : Montant maximum du marché pour un marché non alloti.
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


    "montant_ht_lots": {
        "consigne": """MONTANT_HT_LOTS
     Définition : Montant hors taxes maximum de chaque lot du marché.
     Indices : 
     - Dans la section spécifique des montants maximums hors taxes des lots du marché, ou dans la forme du marché.
     - Si le marché est alloti, alors il y a un montant maximumpour chaque lot.
     - Si le marché n'est pas alloti, renvoyer []
     - Pour chaque montant hors taxes, indiquer si le montant maximum est annuel ou pour toute la durée du marché.
     Format : une liste de json au format suivant [{"numero_lot": le numéro du lot, 'montant_ht_maximum': le montant hors taxes maximum du lot, 'type_montant': 'annuel' ou 'total'}, {...}]
""",
        "search": "",
        "output_field": "montant_ht_lots",
        "schema":
        {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numero_lot": {"type": "integer"},
                    "montant_ht_maximum": {"type": "string"},
                    "type_montant": {"type": "string", "enum": ["annuel", "total"]}
                },
                "required": ["numero_lot", "montant_ht_maximum", "type_montant"]
            }
        }
    },

    "ccag": {
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

#     "formule_revision_prix": {
#         "consigne": """FORMULE_REVISION_PRIX
#      Définition : Formule de révision des prix
#      Indices : 
#      - Dans la section spécifique de la formule de révision des prix.
#      - La formule de révision est souvent de la forme "C = ..."
#      Format : [la formule mathématiques de révision des prix, la définition des variables]
# """,
#         "search": "",
#         "output_field": "formule_revision_prix"
#     },

#     "index_reference": {
#         "consigne": """INDEX_REFERENCE_CCAP
#      Définition : Index de référence
#      Indices : 
#      - Dans une section spécifique de l'index de référence.
#      Format : le nom de l'index de référence.
# """,
#         "search": "",
#         "output_field": "index_reference"
#     },

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
        "schema":
        {
            "type": "object",
            "properties": {
                "condition_declenchement": {"type": "string"},
                "montant_avance": {"type": "string"},
                "montant_reference": {"type": "string"},
                "remboursement": {"type": "string"}
            },
            "required": [
                "condition_declenchement",
                "montant_avance",
                "montant_reference",
                "remboursement"
            ]
        }
    }

}

#     "revision_prix": {
#         "consigne": """REVISION_PRIX
#      Définition : Les prix sont révisables ou fermes.
#      Indices : 
#      - Dans la section spécifique de la formule de révision des prix.
#      - Si les prix sont fermes, renvoyer "Prix fermes".
#      - Sinon, renvoyer "Prix révisables".
# """,
#         "search": "",
#         "output_field": "revision_prix"
#     },



