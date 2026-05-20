"""
Définitions des attributs à extraire pour les documents de type "sous_traitance".
"""

from .common import (
    ADMINISTRATION_BENEFICIAIRE,
    ADRESSE_POSTALE_TITULAIRE,
    CONSERVE_AVANCE_SOUS_TRAITANT,
    DATE_SIGNATURE_DERNIERE,
    DESCRIPTION_PRESTATIONS,
    MONTANT_TVA,
    OBJET_MARCHE,
    SCHEMA_ADRESSE_POSTALE,
    SCHEMA_DUREE,
    SCHEMA_RIB,
    SOCIETE_PRINCIPALE,
)

SOUS_TRAITANCE_ATTRIBUTES = {
    "administration_beneficiaire": ADMINISTRATION_BENEFICIAIRE,
    "objet_marche": OBJET_MARCHE,
    "societe_principale": SOCIETE_PRINCIPALE,
    "adresse_postale_titulaire": ADRESSE_POSTALE_TITULAIRE,
    "siret_titulaire": {
        "consigne": """
   Définition : Numéro SIRET du titulaire principal du marché, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", "numéro d'immatriculation" ou "SIRET du titulaire".
   - Rechercher dans la section du titulaire principal du marché.
   - Favoriser les numéros de SIRET indiqués dans l'identification du titulaire, plutôt qu'en signature du document.
   - Si plusieurs SIRET sont disponibles pour une même entreprise, avec différentes terminaisons (5 derniers chiffres) :
        * Prendre le numéro de l'établissement concerné (pas le siège social) pour renvoyer le SIRET.
        * S'il n'y a pas de précisions sur l'établissement concerné, renvoyer le SIRET le plus élevé.
            -> Exemple : 123 456 789 00001 et 123 456 789 00020, renvoyer 12345678900020 (car 00020 > 00001).
   - Si le numéro de SIRET ne contient pas suffisamment de caractères, ne pas compléter : renvoyer tel quel.
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
    },
    "societe_sous_traitant": {
        "consigne": """
     Définition : Société sous-traitante qui réalise une partie des prestations du marché.  
     Indices : 
     - Rechercher les mentions de société, entreprise, sous-traitant dans la section dédiée à la sous-traitance.
     - Le nom de la société sous-traitante est généralement distinct de la société principale.
     Format : renvoyer le nom de la société sous-traitante telle qu'écrit dans le document.
""",
    },
    "adresse_postale_sous_traitant": {
        "consigne": """
     Définition : Adresse postale  de la société sous-traitant (json).
     Indices : 
     - Rechercher l'adresse postale indiquée sur la sous-traitance. 
     - Extraire tous les éléments disponibles :
        * le numéro de voie
        * le nom de la voie
        * le complément d'adresse éventuel (bâtiment, étage, BP, etc.)
        * le code postal
        * la ville
        * le pays (indiquer 'France' si le pays n'est pas mentionné mais implicite)
     - Si aucune adresse trouvée pour le sous-traitant, renvoyer {}
     Format : un json sous format suivant : {'numero_voie': 'le numéro de voie', 'nom_voie': 'le nom de la voie', 'complement_adresse': 'le complément d'adresse éventuel', 'code_postal': 'le code postal', 'ville': 'la ville','pays': 'le pays'}
""",
        "schema": SCHEMA_ADRESSE_POSTALE,
    },
    "siret_sous_traitant": {
        "consigne": """
   Définition : Numéro SIRET du sous-traitant, composé de 14 chiffres.  
   Indices :
   - Peut être mentionné comme "SIRET", "numéro d'immatriculation" ou "SIRET du sous-traitant".
   - Rechercher dans la section du sous-traitant.
   - Favoriser les numéros de SIRET indiqués dans l'identification du sous-traitant, plutôt qu'en signature du document.
   - Si plusieurs SIRET sont disponibles pour une même entreprise, avec différentes terminaisons (5 derniers chiffres) :
        * Prendre le numéro de l'établissement concerné (pas le siège social) pour renvoyer le SIRET.
        * S'il n'y a pas de précisions sur l'établissement concerné, renvoyer le SIRET le plus élevé.
            -> Exemple : 123 456 789 00001 et 123 456 789 00020, renvoyer 12345678900020 (car 00020 > 00001).
   - Si le numéro de SIRET ne contient pas suffisamment de caractères, ne pas compléter : renvoyer tel quel.
   Format : un numéro composé de 14 chiffres, sans espaces.  
""",
    },
    "montant_sous_traitance_ht": {
        "consigne": """
     Définition : Montant de la sous-traitance hors taxes (également hors TVA).  
     Indices : 
     - Rechercher les mentions "hors taxes", "HT", "sans TVA" ou équivalent dans la section sous-traitance. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Si plusieurs montants sont mentionnés pour DGPF et BPU, renvoyer le montant HT correspondant au DGPF.
     - Ne rien envoyer si aucun montant trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
     """,
    },
    "montant_sous_traitance_ttc": {
        "consigne": """
     Définition : Montant de la sous-traitance toutes taxes comprises (ou avec TVA incluse).  
     Indices : 
     - Rechercher les expressions "TTC", "TVA incluse", "TVA comprise" dans la section sous-traitance. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Si plusieurs montants sont mentionnés pour DGPF et BPU, renvoyer le montant TTC correspondant au DGPF.
     - Ignorer les montants HT (hors taxes) et le montant de TVA seule
     - Ne rien envoyer si aucun montant trouvé.
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
    },
    "description_prestations": DESCRIPTION_PRESTATIONS,
    "date_signature": DATE_SIGNATURE_DERNIERE,
    "montant_tva": MONTANT_TVA,
    "paiement_direct": {
        "consigne": """
     Définition : Indique si le sous traitant est eligible au paiement direct.
     Indices : 
     - Rechercher les expressions "eligible au paiement direct", "eligible au paiement indirect", "eligible au paiement en direct", "eligible au paiement en indirect", "eligible au paiement directement", "eligible au paiement indirectement".
     - Ne rien renvoyer si aucune indication trouvée.
     Format : "oui" ou "non".
""",
        "schema": {
            "type": "string",
            "enum": ["oui", "non", ""],
        },
    },
    "rib_sous_traitant": {
        "consigne": """
     Définition : Informations bancaires (IBAN en priorité) du compte à créditer indiqué dans la sous-traitance.
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
     - Si aucune information bancaire trouvée pour le sous-traitant (ni IBAN, ni informations seules), renvoyer {}.
     - Si un seul numéro à 11 chiffres est fourni, il s'agit souvent du numero de compte. Exemple: Numéro de compte: 12345678901. Renvoyer le numéro de compte seul.
     Format :
     - 1er cas (prioritaire) : un json sous format suivant {"banque": "nom de la banque", "iban": "IBAN avec espaces tous les 4 caractères"}
     - 2ème cas (secondaire - uniquement s'il n'y a pas d'IBAN) : un json sous format suivant {"banque": "nom de la banque", "code_banque": "code de la banque à 5 chiffres", "code_guichet": "code du guichet à 5 chiffres", "numero_compte": "numéro de compte à 11 chiffres", "cle_rib": "clé du RIB à 2 chiffres"}
""",
        "schema": SCHEMA_RIB,
    },
    "conserve_avance": CONSERVE_AVANCE_SOUS_TRAITANT,
    "duree_sous_traitance": {
        "consigne": """
        Définition : Durée de la sous-traitance totale exprimée en mois et extension possible.
        Indices :
        - Chercher dans le paragraphe indiquant la durée de la sous-traitance ou le délai d'exécution des prestations.
        - Durée initiale : la durée de la sous-traitance ferme (sans reconduction ou tranches optionnelles), en nombre de mois.
            * En l'absence de précisions sur la durée ferme, par exemple s'il y a seulement des dates de début et de fin, renvoyer duree_initiale: null
            * Exemple : une durée de 1 an, renvoyer 12. une durée de 2 semaines, renvoyer 1.
        - Extension de durée possible : extension maximale en nombre de mois.
            * En l'absence d'informations claires, renvoyer duree_reconduction: null
            * Si des reconductions sont précisées (ne pas confondre avec des tranches optionnelles qui sont gérées ci-dessous) :
                1. duree_reconduction : Trouver la durée d'une reconduction (en nombre de mois). Si l'information n'est pas précisée ou qu'il n'y a pas de reconduction, renvoyer null.
                2. nb_reconductions : Trouver le nombre de reconductions possibles (éventuellement 0). Si l'information n'est pas précisée ou qu'il n'y a pas de reconduction, renvoyer null.
            * Si des tranches optionnelles sont précisées : renvoyer la durée de l'ensemble des tranches optionnelles.
                1. delai_tranche_optionnelle : Trouver la durée de l'ensemble des tranches optionnelles. Si l'information n'est pas précisée ou qu'il n'y a pas de tranches optionnelles, renvoyer null.
                    Exemple : 2 tranches optionnelles de 8 mois, renvoyer 8 + 8 = 16.
        Format : un json sous format suivant {"duree_initiale": "nombre entier de mois", "duree_reconduction": "nombre entier de mois", "nb_reconductions": "nombre entier de reconductions possibles", "delai_tranche_optionnelle": "nombre entier de mois"}
    """,
        "schema": SCHEMA_DUREE,
    },
}
