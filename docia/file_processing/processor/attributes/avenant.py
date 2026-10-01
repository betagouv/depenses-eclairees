"""
Définitions des attributs à extraire pour les documents de type "avenant".
"""

from .common import (
    ADMINISTRATION_BENEFICIAIRE,
    COTRAITANTS,
    ID_MARCHE,
    OBJET_MARCHE,
    SCHEMA_MONEY_BLOCK,
    SIREN_MANDATAIRE,
    SIRET_MANDATAIRE,
    SOCIETE_PRINCIPALE,
)

AVENANT_ATTRIBUTES = {
    "numero_avenant": {
        "consigne": """
   Définition : clé d'identification de l'avenant, comptant le nombre de modifications apportées au contrat (1er avenant, 2e avenant, etc.) ou la désignation explicite du numéro d'avenant dans le document.
   Indices :
   - Rechercher « avenant n° », « 1er avenant », « avenant unique », titres ou mentions en tête d'acte.
   - Ne pas confondre avec l'identifiant du marché (référence administrative du contrat).
   Format : chaîne ou entier cohérent avec le document (ex. "1", "2"). Renvoyer une chaîne vide si absent.
""",
    },
    "administration_beneficiaire": ADMINISTRATION_BENEFICIAIRE,
    "societe_principale": SOCIETE_PRINCIPALE,
    "siret_mandataire": SIRET_MANDATAIRE,
    "siren_mandataire": SIREN_MANDATAIRE,
    "cotraitants": COTRAITANTS,
    "objet_marche": OBJET_MARCHE,
    "id_marche": ID_MARCHE,
    "date_marche": {
        "consigne": """
   Définition : éléments de calendrier du marché initial (notification, durée d'exécution, fin d'exécution) tels que rappelés ou applicables dans l'avenant.
   Indices :
   - Date de notification, durée d'exécution en mois, date de fin d'exécution, mentions « à compter du », « pour une durée de ».
   - duree_execution : durée en nombre de mois explicitement mentionnée dans le document. Renvoyer null si absent. 
   - Rechercher la durée avant avenant. Si 12 mois reconductible 3 fois 12 mois, renvoyer 12+3*12 = 48
   - date_notification, date_fin_execution : format strict JJ/MM/AAAA ; null si absent.
   - Ne pas reprendre la date d'un avenant intermédiaire, uniquement la date du marché initial.
   - Ne pas calculer la durée entre deux dates, renvoyer la durée explicitement mentionnée dans le document.
   Format : un objet JSON strict :
   {"duree_execution": "<chaîne>", "date_notification": "<chaîne JJ/MM/AAAA>", "date_fin_execution": "<chaîne JJ/MM/AAAA>"}
""",
        "schema": {
            "type": "object",
            "properties": {
                "duree_execution": {"type": ["integer", "null"]},
                "date_notification": {"type": ["string", "null"]},
                "date_fin_execution": {"type": ["string", "null"]},
            },
            "required": ["duree_execution", "date_notification", "date_fin_execution"],
        },
    },
    "montant_initial": {
        "consigne": """
   Définition : montants du marché initial, avant tous les avenants — montant de base du contrat à l'origine (notification / acte initial).
   Indices :
   - Rechercher les montants HT, TVA, TTC, taux de TVA rappelés comme « montant initial », « montant du marché initial », « montant à la notification », « montant du contrat initial ».
   - Ne pas confondre avec l'incidence financière de l'avenant (delta), le montant après le dernier avenant (champ montant_marche) ni le montant d'un avenant intermédiaire seul.
   - Renvoyer toutes les valeurs à null si aucun montant initial n'est mentionné dans le document.
   - Les montants doivent être exprimés en "XXXX.XX" (sans séparateur de milliers, avec 2 décimales)
   - "taux_tva" doit être exprimé en ratio (ex: 0.20, 0.085), pas en pourcentage.
   Format : objet JSON {"ht": ..., "taux_tva": ..., "tva": ..., "ttc": ...} avec null pour chaque clé non mentionnée, ou null pour l'objet entier si absent.
""",
        "schema": SCHEMA_MONEY_BLOCK,
    },
    "montant_marche": {
        "consigne": """
   Définition : montants du marché avant application du présent avenant — état contractuel courant avant incidence financière de l'avenant.
   Indices :
   - Renvoyer la même valeur que montant_initial s'il n'y a que le montant initial mentionné dans le document.      
   - Rechercher le « nouveau montant », « montant révisé », montants HT/TTC/TVA du marché avant application de l'incidence financière de l'avenant.
   - Ne pas confondre avec montant_initial (avant tous les avenants) ni avec incidence_financiere (seul delta de l'avenant) 
   - Ne pas renvoyer le montant actualisé après application du présent avenant, renvoyer le montant avant application de l'incidence financière de l'avenant.
   - Les montants doivent être exprimés en "XXXX.XX" (sans séparateur de milliers, avec 2 décimales)
   - "taux_tva" doit être exprimé en ratio (ex: 0.20, 0.085), pas en pourcentage.
   Format : objet JSON {"ht": ..., "taux_tva": ..., "tva": ..., "ttc": ...} avec null pour chaque clé non mentionnée.
""",
        "schema": SCHEMA_MONEY_BLOCK,
    },
    "objet_avenant": {
        "consigne": """
    Définition : formulation synthétique de la portée de cet avenant uniquement (ce que modifie ou complète l'avenant par rapport au marché initial).
    Indices :
    - Sections « objet de l'avenant », « il a été convenu », modifications contractuelles, liste de clauses modifiées résumée de façon concise.
    Format :
    - En bon français.
    - Ne pas inclure de préfixe de type de document inutile.
    - Chaîne vide si non identifiable.
""",
    },
    "incidence_signataires": {
        "consigne": """
   Définition : incidence de l'avenant sur les signataires ou dénominations (administration ou société) — remplacements de libellés, changement de ministère, de raison sociale, etc.
   Indices :
   - Articles modifiant les mentions de parties, « X est remplacé par Y », tableaux de correspondance.
   Format : objet JSON {"administration_principale": "<texte ou vide>", "societe_principale": "<texte ou vide>"}. Renseigner uniquement ce qui change ; chaîne vide si pas d'incidence pour ce volet.
""",
        "schema": {
            "type": "object",
            "properties": {
                "administration_principale": {"type": ["string", "null"]},
                "societe_principale": {"type": ["string", "null"]},
            },
            "required": ["administration_principale", "societe_principale"],
        },
    },
    "incidence_revision": {
        "consigne": """
   Définition : incidence de l'avenant sur la révision des prix (nouvelle formule, nouvelle base, maintien, suppression, etc.).
   Indices :
   - Clauses de révision, indexation, formules M0, dates anniversaires, références aux conditions économiques.
   Format : objet JSON {"revision": "<texte descriptif ou null>"}.
""",
        "schema": {
            "type": "object",
            "properties": {"revision": {"type": ["string", "null"]}},
            "required": ["revision"],
        },
    },
    "incidence_bpu": {
        "consigne": """
   Définition : l'avenant a-t-il une incidence sur le bordereau des prix unitaires (BPU) ?
   Indices :
   - Mentions de BPU, de prix unitaires, de bordereau annexé modifié, actualisation des prix unitaires.
   Format : booléen true si oui, false si non ou si le document exclut explicitement une telle incidence.
""",
        "schema": {"type": "boolean"},
    },
    "incidence_duree": {
        "consigne": """
   Définition : incidence de l'avenant sur la durée du marché (prolongation en mois, report de date de fin, etc.).
   Indices :
   - « prorogé », « prolongation de X mois », nouvelle date de fin d'exécution.
   Important : prolongation et date_fin_execution sont des chaînes uniquement (pas de type date) ; date_fin_execution au format texte présent dans le document
   Format : objet JSON {"prolongation": "<nombre de mois>", "date_fin_execution": "<date JJ/MM/AAAA>"}.
""",
        "schema": {
            "type": "object",
            "properties": {
                "prolongation": {"type": ["integer", "null"]},
                "date_fin_execution": {"type": ["string", "null"]},
            },
            "required": ["prolongation", "date_fin_execution"],
        },
    },
    "incidence_financiere": {
        "consigne": """
   Définition : variation financière induite par cet avenant uniquement, exprimée en delta (hausse ou baisse) par rapport au montant avant cet avenant — pas le montant total du marché.
   Indices :
   - Montants « supplémentaires », « augmentation », « variation », tableaux de delta HT/TTC.
   - Ne pas confondre avec montant_initial (total avant tous les avenants) ni montant_marche (total après le dernier avenant).
   - Si aucune incidence financière : renvoyer null pour l'objet entier ; dans ce cas montant_marche doit reprendre montant_initial.
   - Les montants doivent être exprimés en "XXXX.XX" (sans séparateur de milliers, avec 2 décimales)
   - "taux_tva" doit être exprimé en ratio (ex: 0.20, 0.085), pas en pourcentage.
   Format : même structure que montant_initial : {"ht": ..., "taux_tva": ..., "tva": ..., "ttc": ...} avec null pour chaque clé non applicable.
""",
        "schema": SCHEMA_MONEY_BLOCK,
    },
    "incidence_autre": {
        "consigne": """
   Définition : description libre d'une autre incidence de l'avenant qui ne relève pas des champs dédiés (financière, signataires, révision des prix, BPU, durée).
   Indices :
   - Modifications contractuelles, clauses ou impacts non couverts par les autres champs d'incidence.
   - Ne pas dupliquer le contenu déjà attendu dans incidence_financiere, incidence_signataires, incidence_revision, incidence_bpu ou incidence_duree.
   Format : texte libre en bon français ; chaîne vide si aucune autre incidence identifiable.
""",
    },
    "date_signature_mandataire": {
        "consigne": """
   Définition : Date de signature de l'avenant par le mandataire (entreprise prestataire principale).
   Indices :
   - Uniquement la date de signature de l'entreprise mandataire, pas celle de l'administration bénéficiaire.
   - Souvent la première date de signature en cas de plusieurs dates de signature.
   - Repérer les expressions comme "Signé le", "Fait à ...", ou des dates en bas du document associées à une signature.
     * Si une date est indiquée après "date de signature" ou "Signé le", on considère l'avenant comme signé,
       même si la signature n'apparaît pas dans le texte extrait.
   - Ignorer les dates d'émission ou de création du document, en général en haut du document.
   - Ne rien renvoyer si aucune date de signature trouvée pour le mandataire.
   Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine.
""",
    },
    "date_signature_administration": {
        "consigne": """
   Définition : Date de signature de l'avenant par l'administration.
   Indices :
   - Uniquement la date de signature de l'acheteur, du pouvoir adjudicateur, ou de l'administration bénéficiaire.
   - Souvent la dernière signature en cas de plusieurs dates de signatures.
   - Repérer les expressions comme "Signé le", "Fait à ...", "signature électronique", ou des dates en bas du document associées à une signature.
     * Si une date est indiquée après "date de signature" ou "Signé le", on considère l'avenant comme signé,
       même si la signature n'apparaît pas dans le texte extrait.
   - Si le document termine par une date seule, c'est probablement la date de signature de l'administration.
   - Parfois la signature est électronique : seuls le nom du signataire et la date apparaissent dans le texte.
   - Ignorer les dates d'émission ou de création du document, en général en haut du document.
   - Ne rien renvoyer si aucune date de signature trouvée.
   Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine.
""",
    },
    "date_notification": {
        "consigne": """
   Définition : Date de notification de cet avenant aux mandataires.
   Indices :
   - Parfois en début du document, ou en toute fin de document.
   - Après la mention "Date de notification" relative à l'avenant, pas la date de début prévisionnelle "Date de début du marché".
   - S'il y a un doute sur la lecture de la date, prendre la date la plus proche postérieure à la signature par l'administration si disponible.
   - Peut aussi être la date d'un courrier de notification ou d'un mail en annexe du document.
   - S'il n'y a pas de date de notification explicite de l'avenant, ne rien renvoyer.
   - Attention à ne pas confondre la date de notification avec la date de signature.
   - Ne pas confondre avec la date de notification du marché initial (champ date_marche.date_notification).
   Format : en "JJ/MM/AAAA" quelle que soit la notation d'origine.
""",
    },
}
