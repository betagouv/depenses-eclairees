import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import tqdm

import pandas as pd

from app.data.sql.sql import bulk_update_attachments
from app.grist import API_KEY_GRIST, URL_TABLE_ATTACHMENTS, update_records_in_grist
from app.utils import getDate
from docia.file_processing.llm.client import LLMClient
from app.data.sql.sql import bulk_update_attachments


logger = logging.getLogger("docia." + __name__)


def create_classification_prompt(filename: str, text: str, list_classification: dict) -> str:
    system_prompt = "Vous êtes un assistant qui aide à classer des fichiers en fonction de leur contenu."
    prompt = f"""
    A partir du contenu du fichier, vous devez déterminer à quelles catégories le document appartient parmi les catégories suivantes. 
    La réponse est une liste de catégories possibles, classée par ordre de correspondance avec le contenu du document.
    
    Voici la liste des catégories possibles :
    {',\n'.join([f"'{v['nom_complet']}': {v['description']}" if v['description']!='' else f"'{v['nom_complet']}'" for v in list_classification.values()])}
    
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


def classify_file_with_llm(filename: str, text: str, list_classification: dict,
                           llm_model: str = 'openweight-medium') -> str:
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
            "schema": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            }
        }
    }

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

    response = llm_env.ask_llm(messages=messages, model=llm_model, response_format=response_format)

    
    # Convertir la (nouvelle) réponse (list) en clé de classification (on prend la première catégorie trouvée)
    if not response or not isinstance(response, list):
        return 'Non classifié'

    reversed_classification_ref = {value['nom_complet']: key for key, value in list_classification.items()}
    result_classif_keys = []
    for classif in response:
        key_classif = reversed_classification_ref.get(classif)
        if key_classif:
            result_classif_keys.append(key_classif)

    return result_classif_keys


def classify_files(dfFiles: pd.DataFrame, list_classification: dict,
                  llm_model: str = 'openweight-medium',
                  max_workers: int = 4) -> pd.DataFrame:
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
    dfFilesClassified['classification'] = None

    # Fonction pour traiter une ligne
    def process_row(idx):
        row = dfFilesClassified.loc[idx]
        filename = row['filename']
        
        result = {
            'classification': None
        }
        
        text = row['text']
        try:
            response_classif = classify_file_with_llm(
                filename=filename,
                text=text,
                list_classification=list_classification,
                llm_model=llm_model
            )
        except Exception as e:
            logger.exception("Erreur lors de la classification LLM de %r: %s", filename, e)
            response_classif = ['Non classifié']
        result['classification'] = response_classif
    
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
        "nom_court": "Abondement",
        "description": "Document justifiant une demande d'abondement de crédit.",
    },
    "acte_engagement": {
        "nom_complet": "Acte d'engagement",
        "nom_court": "Acte d'engagement",
        "description": (
            "Un acte d’engagement est un document contractuel par lequel le titulaire d’un marché "
            "public ou d’un contrat administratif s’engage formellement à exécuter les prestations "
            "prévues, conformément aux conditions définies par l’acheteur, et qui scelle juridiquement "
            "l’accord des parties."
        ),
    },
    "att_etrangers": {
        "nom_complet": "Attestation travailleurs étrangers",
        "nom_court": "Att. travailleurs étrangers",
        "description": "",
    },
    "att_fiscale": {
        "nom_complet": "Attestation fiscale",
        "nom_court": "Att. fiscale",
        "description": "",
    },
    "att_handicap": {
        "nom_complet": "Attestation handicap (AGEFIPH)",
        "nom_court": "Att. handicap",
        "description": "",
    },
    "att_honneur": {
        "nom_complet": "Attestation sur l'honneur",
        "nom_court": "Att. sur l'honneur",
        "description": "",
    },
    "att_resp_civile": {
        "nom_complet": "Attestation responsabilité civile professionnelle",
        "nom_court": "Att. RC pro",
        "description": "",
    },
    "att_sirene": {
        "nom_complet": "Attestation Sirene/Siret",
        "nom_court": "Att. Sirene/Siret",
        "description": "Situation au répertoire SIRENE fournie généralement par l'INSEE.",
    },
    "att_sociale": {
        "nom_complet": "Attestation sociale",
        "nom_court": "Att. sociale",
        "description": "",
    },
    "avenant": {
        "nom_complet": "Avenant",
        "nom_court": "Avenant",
        "description": (
            "Avenant d'un 'Acte d'engagement' (autre document spécifique). "
            "L'avenant a souvent la même forme qu'un acte d'engagement et "
            "comprend 'avenant' dans son titre."
        ),
    },
    "avis_boamp": {
        "nom_complet": "Avis BOAMP",
        "nom_court": "Avis BOAMP",
        "description": "",
    },
    "bon_de_commande": {
        "nom_complet": "Bon de commande",
        "nom_court": "Bon de commande",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) qui "
            "confirme l'accord de l'achat, généralement sur la base d'un devis ou "
            "d'une proposition commerciale. Peut comprendre les annexes au bon de commande.."
        ),
    },
    "bordereau_prix": {
        "nom_complet": "Bordereau de prix unitaire",
        "nom_court": "BPU",
        "description": (
            "Document récapitulatif des prix unitaires proposés dans le cadre du marché, "
            "aussi annexe financière du marché."
        ),
    },
    "ca_chgt_rib": {
        "nom_complet": "CA de changement de rib",
        "description": "Document administratif émis par l'administration (ou l'acheteur) pour préciser des changements sur le rib d'un prestataire.",
    },
    "ccap": {
        "nom_complet": "CCAP (Cahier des Clauses Administratives Particulières)",
        "nom_court": "CCAP",
        "description": "Cahier des charges administratives spécifiant les exigences administratives du marché.",
    },
    "ccap_annexe": {
        "nom_complet": "CCAP annexe autre",
        "description": "Annexe au CCAP contenant des informations complémentaires non repertoriées dans les autres catégories.",
    },
    "ccap_annexe_beneficiaires": {
        "nom_complet": "CCAP annexe bénéficiaires",
        "description": "Annexe au CCAP contenant la liste des bénéficiaires potentiels du marché.",
    },
    "ccp_simple": {
        "nom_complet": "Cahier des clauses Particulières simple",
        "description": "Cahier des charges particuliers valant à la fois cahier des charges administratives et techniques, mais ne valant pas acte d'engagement (un autre document d'engagement est nécessaire).",
    },
    "ccp_vae": {
        "nom_complet": "CCP valant acte d'engagement",
        "description": "Cahier des charges particuliers (administratives et techniques) valant acte d'engagement.",
    },
    "cctp": {
        "nom_complet": "CCTP (Cahier des Clauses Techniques Particulières)",
        "nom_court": "CCTP",
        "description": "Cahier des charges techniques spécifiant les exigences techniques du marché.",
    },
    "commentaire": {
        "nom_complet": "Commentaire",
        "nom_court": "Commentaire",
        "description": "Document spécifique à Chorus coeur, format txt.",
    },
    "conv_financement": {
        "nom_complet": "Convention de financement",
        "nom_court": "Conv. financement",
        "description": "",
    },
    "decomposition_prix": {
        "nom_complet": "Décomposition du prix",
        "nom_court": "Décomposition prix",
        "description": (
            "Document présentant la décomposition du prix d'un achat public. "
            "Souvent appelé Décomposition du prix global forfaitaire."
        ),
    },
    "delegation_pouvoir": {
        "nom_complet": "Délégation de pouvoir",
        "nom_court": "Délégation pouvoir",
        "description": "Document permettant de déléguer une signature ou un pouvoir à une autre personne.",
    },
    "detail_quantitatif_estimatif": {
        "nom_complet": "Detail quantitatif estimatif",
        "nom_court": "DQE",
        "description": (
            "Document présentant le détail quantitatif estimatif d'un marché public, "
            "donne une idée de la quantité de commande sur l'année."
        ),
    },
    "devis": {
        "nom_complet": "Devis",
        "nom_court": "Devis",
        "description": (
            "Devis en amont de la commande. Ressemble parfois à une facture, "
            "mais prévisionnelle ou à payer une fois le service réalisé. Les "
            "propositions ou offres commerciales sont également des devis."
        ),
    },
    "ej_complexe": {
        "nom_complet": "EJ complexe",
        "nom_court": "EJ complexe",
        "description": "Formulaire de déclaration ou création d'un EJ complexe.",
    },
    "facture": {
        "nom_complet": "Facture",
        "nom_court": "Facture",
        "description": (
            "Document émis par un prestataire à l'administration (ou l'acheteur) "
            "pour facturer un service rendu. Attention, une facture s'adresse à "
            "l'administration, elle ne vient pas de l'administration."
        ),
    },
    "fiche_achat": {
        "nom_complet": "Fiche d'achat ou de marché",
        "nom_court": "Fiche d'achat",
        "description": (
            "Fiche d'achat ou de marché servant à préparer la rédaction d'un "
            "marché ou l'émission d'un bon de commande. Les demandes d'achat "
            "sont considérées comme des fiches d'achat."
        ),
    },
    "fiche_communication": {
        "nom_complet": "Fiche de communication ou de transmission",
        "nom_court": "Fiche communication",
        "description": (
            "Fiche de communication entre les logiciels PLACE et Chorus. Les fiches "
            "de communication ou fiches Chorussont également des fiches communication."
        ),
    },
    "fiche_engagement": {
        "nom_complet": "Fiche d'engagement",
        "nom_court": "Fiche d'engagement",
        "description": (
            "Fiche interne demandant l'engagement d'une commande auprès d'un "
            "service juridique, marché ou affaires financières."
        ),
    },
    "fiche_modificative": {
        "nom_complet": "Fiche modificative d'une fiche navette",
        "nom_court": "Fiche modificative",
        "description": (
            "Contient la mention explicite 'Fiche modificative' au début du document. "
            "Fiche de demande de modification, permettant de modifier les informations "
            "dans le logiciel Chorus."
        ),
    },
    "fiche_navette": {
        "nom_complet": "Fiche navette",
        "nom_court": "Fiche navette",
        "description": (
            "Fiche dite navette entre PLACE et Chorus permettant la transmission "
            "d'informations entre les logiciels. Contient la mention explicite de "
            "'Fiche navette' au début du document."
        ),
    },
    "kbis": {
        "nom_complet": "Extrait Kbis",
        "nom_court": "Kbis",
        "description": "",
    },
    "lettre_candidature": {
        "nom_complet": "Lettre de candidature",
        "nom_court": "Lettre candidature",
        "description": "Spécifiquement le formulaire DC1",
    },
    "lettre_candidature_2": {
        "nom_complet": "Lettre de candidature DC2",
        "nom_court": "Lettre candidature DC2",
        "description": "Spécifiquement le formulaire DC2",
    },
    "lettre_consultation": {
        "nom_complet": "Lettre de consultation",
        "nom_court": "Lettre consultation",
        "description": (
            "Document invitant des prestataires à candidater (soumissionner) "
            "à un marché public. Lorsque le document vaut pour engagement, "
            "classifier plutôt acte_engagement."
        ),
    },
    "mail": {
        "nom_complet": "Courrier électronique divers",
        "nom_court": "Courrier",
        "description": "",
    },
    "memoire_technique": {
        "nom_complet": "Mémoire technique",
        "nom_court": "Mémoire technique",
        "description": (
            "Proposition technique d'un candidat à un marché. De formes variées, "
            "comprenant le détail des prestations proposées, souvent des références, ..."
        ),
    },
    "mise_au_point": {
        "nom_complet": "Formulaire de mise au point",
        "nom_court": "Mise au point",
        "description": "",
    },
    "notification": {
        "nom_complet": "Notification",
        "nom_court": "Notification",
        "description": "Notification d'attribution ou de non-attribution d'un marché public.",
    },
    "ordre_service": {
        "nom_complet": "Ordre de service",
        "nom_court": "Ordre de service",
        "description": "Formulaire EXE1 permettant le lancement d'une tranche optionnelle d'un marché.",
    },
    "pv_cao": {
        "nom_complet": "Procès-verbal de Commission d'appel d'offre",
        "nom_court": "PV CAO",
        "description": (
            "Document bilan d'une commission d'attribution d'un marché public, "
            "également les propositions d'attribution."
        ),
    },
    "question_reponse": {
        "nom_complet": "Questions/Réponses",
        "nom_court": "Q/R",
        "description": (
            "Document complémentaire à la consultation des entreprises dans le cadre d'un marché "
            "public comprenant les questions et réponses échangées entre les candidats et le "
            "commanditaire."
        ),
    },
    "rapport_analyse_offre": {
        "nom_complet": "Rapport d'analyse des offres ou de présentation des offres",
        "nom_court": "Rapport analyse offres",
        "description": (
            "Rapport d'analyse des candidatures de prestataires à un marché public "
            "suite à une consultation aux entreprises. Le document compare l'analyse "
            "des offres reçues dans le cadre d'un marché public. Egalement parfois "
            "appelé rapport de présentation."
        ),
    },
    "rapport_signature": {
        "nom_complet": "Rapport de signature",
        "nom_court": "Rapport signature",
        "description": "Document portant uniquement sur le fait d'un autre document a été signé.",
    },
    "rib": {
        "nom_complet": "Relevé d'identité bancaire",
        "nom_court": "RIB",
        "description": "",
    },
    "service_fait": {
        "nom_complet": "Service fait",
        "nom_court": "Service fait",
        "description": "Déclaration de service fait.",
    },
    "sous_traitance": {
        "nom_complet": "Sous-traitance",
        "nom_court": "Sous-traitance",
        "description": "Formulaire de déclaration de sous-traitance d'un marché public. Souvent formulaire 'DC4'",
    }
}


def normalize_text(text):
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.lower()
    text = re.sub(r"[_\-]+", " ", text)  # remplace _ et - par espace
    text = re.sub(r"[^a-z0-9\s]", "", text)  # supprime la ponctuation
    return re.sub(r"\s+", " ", text)  # espaces multiples
