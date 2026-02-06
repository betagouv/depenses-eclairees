import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import tqdm

import pandas as pd

from app.data.sql.sql import bulk_update_attachments
from docia.file_processing.llm.client import LLMClient

logger = logging.getLogger("docia." + __name__)


def create_classification_prompt(filename: str, text: str, list_classification: dict) -> str:
    system_prompt = "Vous êtes un assistant qui aide à classer des fichiers en fonction de leur contenu."
    categories_str = ",\n".join(
        f"'{v['nom_complet']}': {v['description']}" if v["description"] else f"'{v['nom_complet']}'"
        for v in list_classification.values()
    )
    prompt = f"""
    A partir du contenu du fichier, vous devez déterminer à quelles catégories le document appartient 
    parmi les catégories suivantes. La réponse est une liste de catégories possibles, classée par ordre 
    de correspondance avec le contenu du document.
    
    Voici la liste des catégories possibles :
    {categories_str}
    
    Le titre du document est un élément essentiel pour la classification.
    Si le type de document ne correspond à aucune des catégories, répondez "Non classifié".
    
    Voici le nom du document (attention celui-ci peut être trompeur, il faut aussi regarder le contenu) : '{filename}'
    
    Voici la première page du document :
    <DEBUT PAGE>
    '{text[:2000]}'
    <FIN PAGE>

    Format : répondez par une liste de catégories possibles (sans autre texte ni ponctuation).
    """

    return prompt, system_prompt


def classify_file_with_llm(
    filename: str, text: str, list_classification: dict, llm_model: str = "openweight-medium"
) -> str:
    """
    Classifie un fichier en fonction de son contenu en utilisant un LLM.

    Args:
        filename (str): Nom du fichier à classifier
        text (str): Contenu textuel du fichier
        list_classification (dict): Dictionnaire de classification
        api_key (str): Clé API pour le LLM
        base_url (str): URL de base pour le LLM
        llm_model (str): Modèle LLM à utiliser

    Returns:
        str: Classification du fichier
    """
    llm_env = LLMClient()

    prompt, system_prompt = create_classification_prompt(filename, text, list_classification)

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "ClassificationList",
            "strict": True,
            "schema": {"type": "array", "items": {"type": "string"}},
        },
    }

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

    response = llm_env.ask_llm(messages=messages, model=llm_model, response_format=response_format)

    # Convertir la (nouvelle) réponse (list) en clé de classification (on prend la première catégorie trouvée)
    if not response or not isinstance(response, list):
        return "Non classifié"

    reversed_classification_ref = {value["nom_complet"]: key for key, value in list_classification.items()}
    result_classif_keys = []
    for classif in response:
        key_classif = reversed_classification_ref.get(classif)
        if key_classif:
            result_classif_keys.append(key_classif)

    return result_classif_keys[0] if len(result_classif_keys) > 0 else "Non classifié"


def classify_files(
    dfFiles: pd.DataFrame, list_classification: dict, llm_model: str = "openweight-medium", max_workers: int = 4
) -> pd.DataFrame:
    """
    Classifie les fichiers d'un DataFrame entre les différentes pièces jointes possibles.

    Args:
        dfFiles (pd.DataFrame): DataFrame contenant les noms des fichiers et leurs n° d'EJ
        list_classification (dict): Dictionnaire de classification
        llm_model (str): Modèle LLM à utiliser (par défaut: 'openweight-medium')
        max_workers (int): Nombre maximum de threads pour l'exécution parallèle (par défaut: 4)

    Returns:
        pd.DataFrame: DataFrame contenant les informations sur les fichiers avec les colonnes:
            - classification: Type de document classifié (ex: 'devis', 'facture', 'Non classifié')
    """
    dfFilesClassified = dfFiles.copy(deep=False)
    dfFilesClassified["classification"] = None

    # Fonction pour traiter une ligne
    def process_row(idx):
        row = dfFilesClassified.loc[idx]
        filename = row["filename"]

        result = {"classification": None}

        text = row["text"]
        try:
            response_classif = classify_file_with_llm(
                filename=filename, text=text, list_classification=list_classification, llm_model=llm_model
            )
        except Exception as e:
            logger.exception("Erreur lors de la classification LLM de %r: %s", filename, e)
            response_classif = ["Non classifié"]
        result["classification"] = response_classif

        return idx, result

    # Traitement parallèle avec ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_row, i) for i in dfFilesClassified.index]

        for future in tqdm.tqdm(futures, total=len(futures), desc="Classification des fichiers"):
            idx, result = future.result()
            for key, value in result.items():
                dfFilesClassified.at[idx, key] = value

    # dfFilesClassified = dfFilesClassified.astype(str)
    print(f"Nombre de fichiers classifiés : {dfFilesClassified['classification'].value_counts()}")

    return dfFilesClassified


def save_classify_files_result(df: pd.DataFrame):
    bulk_update_attachments(df, ["classification", "classification_type"])


# Catalogue des catégories de pièces jointes (utilisé par la classification LLM)
# Catégories par ordre alphabétique.
DIC_CLASS_FILE_BY_NAME = {
    "abondement": {
        "nom_complet": "Abondement",
        "short_name": "Abondement",
        "description": "Document justifiant une demande d'abondement de crédit.",
    },
    "acte_engagement": {
        "nom_complet": "Acte d'engagement",
        "short_name": "Acte d'engagement",
        "description": (
            "Un acte d’engagement est un document contractuel par lequel le titulaire d’un marché "
            "public ou d’un contrat administratif s’engage formellement à exécuter les prestations "
            "prévues, conformément aux conditions définies par l’acheteur, et qui scelle juridiquement "
            "l’accord des parties."
        ),
    },
    "ae_annexe": {
        "nom_complet": "Annexe à l'acte d'engagement",
        "short_name": "Annexe Act. Eng.",
        "description": "Annexe à un acte d'engagement (autre que dgpf, bpu ou annexe financière).",
    },
    "application_revision_prix": {
        "nom_complet": "Application de révision du prix",
        "short_name": "App. révision prix",
        "description": (
            "Application de révision du prix prévue par le cahier des charges du marché "
            "souvent un document annexe au cahier des charges."
        ),
    },
    "att_etrangers": {
        "nom_complet": "Attestation travailleurs étrangers",
        "short_name": "Att. travailleurs étrangers",
        "description": ("Attestation certifiant la situation des travailleurs étrangers employés par le prestataire."),
    },
    "att_fiscale": {
        "nom_complet": "Attestation fiscale",
        "short_name": "Att. fiscale",
        "description": ("Attestation sur la situation fiscale du prestataire, délivrée par l'administration fiscale."),
    },
    "att_handicap": {
        "nom_complet": "Attestation handicap (AGEFIPH)",
        "short_name": "Att. handicap",
        "description": (
            "Attestation délivrée par l'AGEFIPH certifiant l'emploi de travailleurs handicapés par le prestataire."
        ),
    },
    "att_honneur": {
        "nom_complet": "Attestation sur l'honneur",
        "short_name": "Att. sur l'honneur",
        "description": (
            "Document par lequel le prestataire atteste sur l'honneur de certaines conditions ou situations."
        ),
    },
    "att_resp_civile": {
        "nom_complet": "Attestation responsabilité civile professionnelle",
        "short_name": "Att. RC pro",
        "description": "Attestation d'assurance responsabilité civile professionnelle du prestataire.",
    },
    "att_sirene": {
        "nom_complet": "Attestation Sirene/Siret",
        "short_name": "Att. Sirene/Siret",
        "description": "Situation au répertoire SIRENE fournie généralement par l'INSEE.",
    },
    "att_sociale": {
        "nom_complet": "Attestation sociale",
        "short_name": "Att. sociale",
        "description": (
            "Attestation certifiant la situation sociale du prestataire, "
            "généralement délivrée par l'URSSAF ou un organisme similaire."
        ),
    },
    "avenant": {
        "nom_complet": "Avenant",
        "short_name": "Avenant",
        "description": (
            "Avenant d'un 'Acte d'engagement' (autre document spécifique). "
            "L'avenant a souvent la même forme qu'un acte d'engagement et "
            "comprend 'avenant' dans son titre."
        ),
    },
    "avis_boamp": {
        "nom_complet": "Avis BOAMP",
        "short_name": "Avis BOAMP",
        "description": "Avis de publicité publié au Bulletin Officiel des Annonces de Marchés Publics (BOAMP).",
    },
    "bon_de_commande": {
        "nom_complet": "Bon de commande",
        "short_name": "Bon de commande",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) qui "
            "confirme l'accord de l'achat, généralement sur la base d'un devis ou "
            "d'une proposition commerciale. Peut comprendre les annexes au bon de commande."
        ),
    },
    "bordereau_prix": {
        "nom_complet": "Bordereau de prix unitaire",
        "short_name": "BPU",
        "description": (
            "Document récapitulatif des prix unitaires proposés dans le cadre du marché, "
            "aussi annexe financière du marché."
        ),
    },
    "ca_chgt_denomination": {
        "nom_complet": "CA de changement de dénomination",
        "short_name": "CA chgt. Nom",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) "
            "pour préciser des changements sur la dénomination d'un prestataire."
        ),
    },
    "ca_chgt_ej": {
        "nom_complet": "CA de changement d'EJ",
        "short_name": "CA chgt. EJ",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) pour "
            "préciser des changements sur l'engagement juridique. "
            "Souvent un changement d'imputation ou un changement dans un ligne de poste."
        ),
    },
    "ca_chgt_siret": {
        "nom_complet": "CA de changement de SIRET",
        "short_name": "CA chgt. SIREN / SIRET",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) "
            "pour préciser des changements sur le siret d'un prestataire. "
            "Souvent un changement de siret et une nouvelle adresse postale."
        ),
    },
    "ca_chgt_revision_prix": {
        "nom_complet": "CA de changement de révision du prix",
        "short_name": "CA chgt. Rev. prix",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) "
            "pour préciser des changements sur la révision du prix. "
            "Souvent un changement sur la date d'application de la révision du prix."
        ),
    },
    "ca_chgt_rib": {
        "nom_complet": "CA de changement de rib",
        "short_name": "CA chgt. RIB",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) "
            "pour préciser des changements sur le rib d'un prestataire."
        ),
    },
    "ccag": {
        "nom_complet": "CCAG (Cahier des Clauses Administratives Générales)",
        "short_name": "CCAG",
        "description": (
            "Cahier des charges administratives générales spécifiant les exigences administratives du marché."
        ),
    },
    "ccap": {
        "nom_complet": "CCAP (Cahier des Clauses Administratives Particulières)",
        "short_name": "CCAP",
        "description": "Cahier des charges administratives spécifiant les exigences administratives du marché.",
    },
    "ccap_annexe": {
        "nom_complet": "CCAP annexe autre",
        "short_name": "CCAP annexe autre",
        "description": (
            "Annexe au CCAP contenant des informations complémentaires "
            "(hors bénéficiaires) non repertoriées dans les autres catégories."
        ),
    },
    "ccap_annexe_beneficiaires": {
        "nom_complet": "CCAP annexe bénéficiaires",
        "short_name": "CCAP annexe bénéficiaires",
        "description": "Annexe au CCAP contenant la liste des bénéficiaires potentiels du marché.",
    },
    "ccc": {
        "nom_complet": "CCC (Cahier des Clauses Complementaires)",
        "short_name": "CC Complementaire",
        "description": (
            "Cahier des clauses complémentaires spécifiant les exigences complémentaires du marché."
            "Souvent un document relatif à un marché subséquent d'un marché global. "
            "De la même forme que le cahier des charges."
        ),
    },
    "ccp_simple": {
        "nom_complet": "Cahier des clauses Particulières simple",
        "short_name": "CCP",
        "description": (
            "Cahier des charges particuliers valant à la fois cahier des charges "
            "administratives et techniques, mais ne valant pas acte d'engagement "
            "(un autre document d'engagement est nécessaire)."
        ),
    },
    "ccp_vae": {
        "nom_complet": "CCP valant acte d'engagement",
        "short_name": "CCP valant AE",
        "description": (
            "Cahier des charges particuliers (administratives et techniques) valant acte d'engagement. "
            "C'est à la fois un cahier des charges administratif, un cahier des charges techniques et"
            "un acte d'engagement."
        ),
    },
    "cctp": {
        "nom_complet": "CCTP (Cahier des Clauses Techniques Particulières)",
        "short_name": "CCTP",
        "description": "Cahier des charges techniques spécifiant les exigences techniques du marché.",
    },
    "cctp_annexe": {
        "nom_complet": "CCTP annexe autre",
        "short_name": "CCTP annexe autre",
        "description": (
            "Annexe au CCTP contenant des informations complémentaires non repertoriées dansles autres catégories."
        ),
    },
    "cga": {
        "nom_complet": "CGA (Conditions générales d'achats)",
        "short_name": "CGA",
        "description": "Conditions générales d'achats spécifiant les conditions générales d'achats du marché.",
    },
    "commentaire": {
        "nom_complet": "Commentaire",
        "short_name": "Commentaire",
        "description": "Document spécifique à Chorus coeur, format txt.",
    },
    "conv_financement": {
        "nom_complet": "Convention de financement",
        "short_name": "Conv. financement",
        "description": "Convention définissant les modalités de financement d'un marché ou d'un projet.",
    },
    "reconduction": {
        "nom_complet": "Reconduction",
        "short_name": "Reconduction",
        "description": "Reconduction ou de non-reconduction d'un marché public.",
    },
    "decomposition_prix": {
        "nom_complet": "Décomposition du prix",
        "short_name": "DGPF",
        "description": (
            "Document présentant la décomposition du prix d'un achat public. "
            "Souvent appelé Décomposition du prix global forfaitaire."
        ),
    },
    "delegation_pouvoir": {
        "nom_complet": "Délégation de pouvoir",
        "short_name": "Délégation pouvoir",
        "description": "Document permettant de déléguer une signature ou un pouvoir à une autre personne.",
    },
    "detail_quantitatif_estimatif": {
        "nom_complet": "Détail quantitatif estimatif",
        "short_name": "DQE",
        "description": (
            "Document présentant le détail quantitatif estimatif d'un marché public, "
            "donne une idée de la quantité de commande sur l'année."
        ),
    },
    "devis": {
        "nom_complet": "Devis",
        "short_name": "Devis",
        "description": (
            "Devis en amont de la commande. Ressemble parfois à une facture, "
            "mais prévisionnelle ou à payer une fois le service réalisé. Les "
            "propositions ou offres commerciales sont également des devis."
        ),
    },
    "ej_complexe": {
        "nom_complet": "EJ complexe",
        "short_name": "EJ complexe",
        "description": "Formulaire de déclaration ou création d'un EJ complexe.",
    },
    "facture": {
        "nom_complet": "Facture",
        "short_name": "Facture",
        "description": (
            "Document émis par un prestataire à l'administration (ou l'acheteur) "
            "pour facturer un service rendu. Attention, une facture s'adresse à "
            "l'administration, elle ne vient pas de l'administration."
        ),
    },
    "fiche_achat": {
        "nom_complet": "Fiche d'achat ou de marché",
        "short_name": "Fiche d'achat",
        "description": (
            "Fiche d'achat ou de marché servant à préparer la rédaction d'un "
            "marché ou l'émission d'un bon de commande. Les demandes d'achat "
            "sont considérées comme des fiches d'achat."
        ),
    },
    "fiche_communication": {
        "nom_complet": "Fiche de communication ou de transmission",
        "short_name": "Fiche communication",
        "description": (
            "Fiche de communication entre les logiciels PLACE et Chorus. Les fiches "
            "de communication ou fiches Chorus sont également des fiches communication."
        ),
    },
    "fiche_engagement": {
        "nom_complet": "Fiche d'engagement",
        "short_name": "Fiche d'engagement",
        "description": (
            "Fiche interne demandant l'engagement d'une commande auprès d'un "
            "service juridique, marché ou affaires financières."
        ),
    },
    "fiche_modificative": {
        "nom_complet": "Fiche modificative d'une fiche navette",
        "short_name": "Fiche modificative",
        "description": (
            "Contient la mention explicite 'Fiche modificative' au début du document. "
            "Fiche de demande de modification, permettant de modifier les informations "
            "dans le logiciel Chorus."
        ),
    },
    "fiche_navette": {
        "nom_complet": "Fiche navette",
        "short_name": "Fiche navette",
        "description": (
            "Fiche dite navette entre PLACE et Chorus permettant la transmission "
            "d'informations entre les logiciels. Contient la mention explicite de "
            "'Fiche navette' au début du document."
        ),
    },
    "kbis": {
        "nom_complet": "Extrait Kbis",
        "short_name": "Kbis",
        "description": "Extrait Kbis certifiant l'inscription au registre du commerce et des sociétés (RCS).",
    },
    "lettre_candidature": {
        "nom_complet": "Lettre de candidature",
        "short_name": "Lettre candidature",
        "description": "Spécifiquement le formulaire DC1",
    },
    "lettre_candidature_2": {
        "nom_complet": "Lettre de candidature DC2",
        "short_name": "Lettre candidature DC2",
        "description": "Spécifiquement le formulaire DC2",
    },
    "lettre_consultation": {
        "nom_complet": "Lettre de consultation",
        "short_name": "Lettre consultation",
        "description": (
            "Document invitant des prestataires à candidater (soumissionner) "
            "à un marché public. Lorsque le document vaut pour engagement, "
            "classifier plutôt acte_engagement."
        ),
    },
    "mail": {
        "nom_complet": "Courrier électronique divers",
        "short_name": "Mail",
        "description": (
            "Courrier électronique (email) de nature administrative ou commerciale "
            "non classé dans une autre catégorie spécifique."
        ),
    },
    "memoire_technique": {
        "nom_complet": "Mémoire technique",
        "short_name": "Mémoire technique",
        "description": (
            "Proposition technique d'un candidat à un marché. De formes variées, "
            "comprenant le détail des prestations proposées, souvent des références, ..."
        ),
    },
    "mise_au_point": {
        "nom_complet": "Formulaire de mise au point",
        "short_name": "Mise au point",
        "description": (
            "Formulaire permettant de mettre à jour ou de corriger des informations dans le système de gestion."
        ),
    },
    "notification": {
        "nom_complet": "Notification",
        "short_name": "Notification",
        "description": "Notification d'attribution ou de non-attribution d'un marché public.",
    },
    "ordre_service": {
        "nom_complet": "Ordre de service",
        "short_name": "Ordre de service",
        "description": ("Formulaire EXE1 permettant le lancement d'une tranche optionnelle  d'un marché."),
    },
    "pv_cao": {
        "nom_complet": "Procès-verbal de Commission d'appel d'offre",
        "short_name": "PV CAO",
        "description": (
            "Document bilan d'une commission d'attribution d'un marché public, "
            "également les propositions d'attribution."
        ),
    },
    "question_reponse": {
        "nom_complet": "Questions/Réponses",
        "short_name": "Q/R",
        "description": (
            "Document complémentaire à la consultation des entreprises dans le cadre d'un marché "
            "public comprenant les questions et réponses échangées entre les candidats et le "
            "commanditaire."
        ),
    },
    "rapport_affermissement_tranche": {
        "nom_complet": "Rapport d'affermissement de tranche",
        "short_name": "Rapport affermissement tranche",
        "description": (
            "Rapport d'affermissement de tranche d'un marché public présentant "
            "la décision d'affermissement d'une tranche optionnelle."
        ),
    },
    "rapport_analyse_offre": {
        "nom_complet": "Rapport d'analyse des offres ou de présentation des offres",
        "short_name": "Rapport analyse offres",
        "description": (
            "Rapport d'analyse des candidatures de prestataires à un marché public "
            "suite à une consultation aux entreprises. Le document compare l'analyse "
            "des offres reçues dans le cadre d'un marché public. Egalement parfois "
            "appelé rapport de présentation."
        ),
    },
    "rapport_signature": {
        "nom_complet": "Rapport de signature",
        "short_name": "Rapport signature",
        "description": "Document portant uniquement sur le fait qu'un autre document a été signé.",
    },
    "reglement_consultation": {
        "nom_complet": "Règlement de consultation",
        "short_name": "Règlement consultation",
        "description": "Règlement de consultation d'un marché public présentant les modalités de la consultation.",
    },
    "rib": {
        "nom_complet": "Relevé d'identité bancaire",
        "short_name": "RIB",
        "description": (
            "Relevé d'identité bancaire contenant les coordonnées bancaires du prestataire pour les paiements."
        ),
    },
    "service_fait": {
        "nom_complet": "Service fait",
        "short_name": "Service fait",
        "description": "Déclaration de service fait.",
    },
    "sous_traitance": {
        "nom_complet": "Sous-traitance",
        "short_name": "Sous-traitance",
        "description": ("Formulaire de déclaration de sous-traitance d'un marché public. Souvent formulaire 'DC4'"),
    },
}