"""
Définitions des attributs à extraire pour les documents de type "fiche_navette".
"""

FICHE_NAVETTE_ATTRIBUTES = {
    "administration_beneficiaire": {
        "consigne": """
     Définition : Structure administrative ou publique qui bénéficie de la commande, ou qui achète la prestation.
     Indices :
     - Rechercher les mentions d'acheteurs, de pouvoir adjudicateur, ou d'autorité contractante.
     - Le résultat est souvent une direction, un service, ou une administration.
     - S'il est seulement précisé les rôles ou les postes de persones (ex : le préfet de la région Île-de-France), déduire la direction / le service / l'administration bénéficiaire (ex : la préfecture de la région Île-de-France).
     Format : le nom de l'administration bénéficiaire en toutes lettres (pas d'acronymes si possible). 
""",
    },
    "objet": {
        "consigne": """
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
    },
    "societe_principale": {
        "consigne": """
     Définition : Société principale contractante avec l'administration publique ou ses représentants. Si un groupement est mentionné, extraire la société mandataire ou représentante.  
     Indices : 
     - Rechercher les mentions de société, entreprise, titulaire, mandataire, contractant ou tiers.
     - En général, l'autre nom de personne morale que l'administration acheteuse.
     - Le nom de la société est souvent cohérent avec le nom de domaine du site interne.
     Format : renvoyer le nom de la société telle qu'écrit dans le document.
""",
    },
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
    "montant_ht": {
        "consigne": """
     Définition : Montant du marché hors taxes (également hors TVA).  
     Indices : 
     - Rechercher les mentions "hors taxes", "HT", "sans TVA" ou équivalent. 
     - Extraire le montant exprimé en euros ou en écriture littérale, et mets le en chiffres en euros.
     - Ne rien envoyer si aucun montant trouvé.
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
}
