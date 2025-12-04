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
""",
        "search": "Section du document qui décrit l'objet du marché ou le contexte général de la consultation.",
        "output_field": "objet_marche_ccap"
    },

    "lots": {
        "consigne": """LOTS
     Définition : Liste des lots du marché.
     Indices : 
     - Rechercher les lots du marché dans la section de l'alotissement.
     - Si une décomposition en lots est mentionnée ailleurs dans le document, alors renvoyer la liste des lots avec les informations trouvées.
     Format : une liste au format python ["Lot 1 : [intitulé]", "Lot 2 : [intitulé]", ...].
""",
        "search": "",
        "output_field": "lots"
    },

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

    "duree_lots": {
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

    "duree_marche": {
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

    "formule_revision_prix": {
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
   Format : {'condition_declenchement':"", 'montant_avance':XX%, 'montant_reference':"", 'remboursement':XX%-XX%}
""",
        "search": "avance accordée titulaire montant initial durée exécution remboursement précompte",
        "output_field": "condition_avance_ccap"
    },

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

    "montant_ht_ccap": {
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

