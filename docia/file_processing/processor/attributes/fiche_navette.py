"""
Définitions des attributs à extraire pour les documents de type "fiche_navette".
"""

from .common import (
    ADMINISTRATION_BENEFICIAIRE,
    MONTANT_HT,
    OBJET,
    SOCIETE_PRINCIPALE,
)

FICHE_NAVETTE_ATTRIBUTES = {
    "administration_beneficiaire": ADMINISTRATION_BENEFICIAIRE,
    "objet": OBJET,
    "societe_principale": SOCIETE_PRINCIPALE,
    "accord_cadre": {
        "consigne": """
     Définition : Libellé de l'accord-cadre
     Indices : Repérer les expressions comme "Libellé accord-cadre".
     Ne rien renvoyer si aucune information trouvée ou si tu trouves l'information du type d'accord-cadre (ex : "accord-cadre mono-attributaire à bons de commande").
""",
    },
    "id_accord_cadre": {
        "consigne": """
     Définition : Identifiant de l'accord cadre 
     Indices : Repérer les identifiants sous la forme "2022AMO0538402"
""",
    },
    "montant_ht": MONTANT_HT,
    "montant_maximum": {
        "consigne": """
     Définition : Montant maximum hors taxes du marché.
     Indices : Repérer les expressions comme "Montant maximum", "Montant maximum HT" ou "Montant maximum hors taxes".
     Ne rien renvoyer si aucune information trouvée ou si tu trouves "Non renseigné".
     Format : en "XXXX.XX€" (sans séparateur de milliers, avec 2 décimales)
""",
    },
    "reconduction": {
        "consigne": """
     Définition : Reconduction ou de non-reconduction d'un marché public.
     Indices : Repérer les expressions comme "Reconduction" ou "Non-reconduction".
     Format : "Oui" ou "Non". Parfois une durée est mentionnée, dans ce cas, renvoyer Oui.
     Ne rien renvoyer si aucune information trouvée ou si tu trouves "Non renseigné".
     """,
    },
    "taux_tva": {
        "consigne": """
     Définition : Taux de la TVA appliquée au marché.
     Indices : Repérer les expressions comme "Taux de la TVA" ou "TVA" ou "TAXE SUR LA VALEUR AJOUTÉE".
     Format : "0.20" ou "0.055" et non "20%" ou "5.5%"
     Ne rien renvoyer si aucune information trouvée ou si tu trouves "Non renseigné".
     """,
    },
    "centre_cout": {
        "consigne": """
     Définition : Identifiant du centre de coût du marché.
     Indices : Repérer les expressions comme "Centre de coût".
     Format : DRIEETR075
""",
    },
    "centre_financier": {
        "consigne": """
     Définition : Identifiant du centre financier du marché.
     Indices : Repérer les expressions comme "Centre financier".
     Format : 0174-CLIM-SCEE
""",
    },
    "activite": {
        "consigne": """
     Définition : Activité du marché.
     Indices : Repérer les expressions comme "Activité".
     Format : 020304DGTUCT
""",
    },
    "domaine_fonctionnel": {
        "consigne": """
     Définition : Domaine fonctionnel du marché.
     Indices : Repérer les expressions comme "Domaine fonctionnel".
     Format : 0203-04-02
""",
    },
    "fond": {
        "consigne": """
     Définition : Fond du marché.
     Indices : Repérer les expressions comme "Fond".
     N/A est une valeur acceptable. Ne pas confondre avec "non renseigné" ou vide.
     Format : 1-1-00733, N/A
""",
    },
    "localisation_interministerielle": {
        "consigne": """
     Définition : Localisation interministérielle du marché.
     Indices : Repérer les expressions comme "Localisation interministérielle".
     Format : N, N11, N9130, N7630189, S1200594 ou B104788 
""",
    },
    "groupe_marchandise": {
        "consigne": """
     Définition : Groupe de marchandise du marché.
     Indices : Repérer les expressions comme "Groupe de marchandise".
     Format : 40.01.02
""",
    },
    "axe_ministeriel_1": {
        "consigne": """
     Définition : Axe ministériel 1 du marché.
     Indices : Repérer les expressions comme "Axe ministériel 1" ou "Axe ministériel".
     Format : 10-SG-SIMJ
""",
    },
    "projet_analytique": {
        "consigne": """
     Définition : Projet analytique du marché.
     Indices : Repérer les expressions comme "Projet analytique".
     Format : code alphanumérique
""",
    },
    "localisation_ministerielle": {
        "consigne": """
     Définition : Localisation ministérielle du marché.
     Indices : Repérer les expressions comme "Localisation ministérielle".
     Format : code alphanumérique
""",
    },
    "axe_ministeriel_2": {
        "consigne": """
     Définition : Axe ministériel 2 du marché.
     Indices : Repérer les expressions comme "Axe ministériel 2".
     Format : 10-SG-SIMJ
""",
    },
    "remarque": {
        "consigne": """
     Définition : Remarque libre associée au marché.
     Indices : Repérer les expressions comme "Remarque".
     Format : texte libre
""",
    },
}
