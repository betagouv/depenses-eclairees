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


def is_expression_in_filename(expression: list[str], filename: str) -> bool:
    """
    Vérifie si la séquence de mots (expression) est présente dans le nom du fichier.

    Args:
        expression (list[str]): Liste de mots formant une expression à chercher
        filename (str): Nom du fichier à analyser

    Returns:
        bool: True si l'expression est trouvée, False sinon
    """
    if not expression:
        return False

    normalized_text = normalize_text(filename)

    match = True
    try:
        for word in expression:
            normalized_word = normalize_text(word)
            match = match and (normalized_word in normalized_text)

        return match
    except Exception as e:
        raise (e)


def classify_file_with_name(filename: str, list_classification={"devis": {"words": ["devis"]}}):
    # Test pour chaque type de document dans la liste de classification
    pClassification = pd.DataFrame(index=list_classification, columns=["score"])
    pClassification["score"] = 0
    for type_document in list_classification:
        # Liste les mots clés associés à ce type de document
        key_words = list_classification[type_document]["words"]
        contain_stopword = False
        try:
            stop_words = list_classification[type_document]["stopwords"]
            # Vérifier si le nom du fichier contient des stopwors
            for word in stop_words:
                if is_expression_in_filename(word, filename):
                    contain_stopword = True
        except KeyError:
            print("Pas de stopwords pour ce type de document")
        if not contain_stopword:
            for word in key_words:
                # Vérifier si le mot est dans le nom du fichier
                if is_expression_in_filename(word, filename):
                    # return type_document
                    pClassification.at[type_document, "score"] = 1
    return (
        pClassification.query("score == 1").index.tolist()
        if pClassification.query("score == 1").shape[0] > 0
        else ["Non classifié"]
    )


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


# Classifications des PJ par type de mots clés recherchés dans les noms
DIC_CLASS_FILE_BY_NAME = {
    "rib": {
        "words": [[" rib"], [" iban"], ["att", "bpi"]],
        "stopwords": [],
        "nom_complet": "Relevé d'identité bancaire",
        "nom_court": "RIB",
        "description": "",
    },
    "kbis": {
        "words": [["kbis"], [" k "], [" bis "]],
        "stopwords": [],
        "nom_complet": "Extrait Kbis",
        "nom_court": "Kbis",
        "description": "",
    },
    "att_sirene": {
        "words": [["sirene"], ["siret"]],
        "stopwords": [],
        "nom_complet": "Attestation Sirene/Siret",
        "nom_court": "Att. Sirene/Siret",
        "description": "Situation au répertoire SIRENE fournie généralement par l'INSEE.",
    },
    "att_fiscale": {
        "words": [["att", "fiscale"]],
        "stopwords": [],
        "nom_complet": "Attestation fiscale",
        "nom_court": "Att. fiscale",
        "description": "",
    },
    "att_sociale": {
        "words": [["att", "sociale"], ["att", "urssaf"]],
        "stopwords": [],
        "nom_complet": "Attestation sociale",
        "nom_court": "Att. sociale",
        "description": "",
    },
    "att_etrangers": {
        "words": [["lnte"], ["trav", "etranger"], ["liste", "nominative"], ["liste", "etranger"]],
        "stopwords": [],
        "nom_complet": "Attestation travailleurs étrangers",
        "nom_court": "Att. travailleurs étrangers",
        "description": "",
    },
    "att_resp_civile": {
        "words": [[" rcp "], ["responsabilité", "civile"], ["rc", "pro"]],
        "stopwords": [],
        "nom_complet": "Attestation responsabilité civile professionnelle",
        "nom_court": "Att. RC pro",
        "description": "",
    },
    "att_honneur": {
        "words": [["att", "honneur"]],
        "stopwords": [],
        "nom_complet": "Attestation sur l'honneur",
        "nom_court": "Att. sur l'honneur",
        "description": "",
    },
    "att_handicap": {
        "words": [["att", "agefiph"]],
        "stopwords": [],
        "nom_complet": "Attestation handicap (AGEFIPH)",
        "nom_court": "Att. handicap",
        "description": "",
    },
    "mise_au_point": {
        "words": [["mise", "au", "point"], ["OUV1"]],
        "stopwords": [],
        "nom_complet": "Formulaire de mise au point",
        "nom_court": "Mise au point",
        "description": "",
    },
    "mail": {
        "words": [["retour", "non", "visé"], ["mel"], ["suivi", "messages"], [" mail "], [" ar ", " ae"]],
        "stopwords": [],
        "nom_complet": "Courrier électronique divers",
        "nom_court": "Courrier",
        "description": "",
    },
    "rapport_signature": {
        "words": [["rapport", "signature"], ["vérification", "signature"]],
        "stopwords": [],
        "nom_complet": "Rapport de signature",
        "nom_court": "Rapport signature",
        "description": "Document portant uniquement sur le fait d'un autre document a été signé.",
    },
    "notification": {
        "words": [["notif"], ["noti6"], ["certificat", "cessibilité"]],
        "stopwords": [],
        "nom_complet": "Notification",
        "nom_court": "Notification",
        "description": "Notification d'attribution ou de non-attribution d'un marché public.",
    },
    "conv_financement": {
        "words": [["conv", "financement"]],
        "stopwords": [],
        "nom_complet": "Convention de financement",
        "nom_court": "Conv. financement",
        "description": "",
    },
    "pv_cao": {
        "words": [["pv", "cao"], ["rejet"]],
        "stopwords": [],
        "nom_complet": "Procès-verbal de Commission d'appel d'offre",
        "nom_court": "PV CAO",
        "description": (
            "Document bilan d'une commission d'attribution d'un marché public, "
            "également les propositions d'attribution."
        ),
    },
    "lettre_consultation": {
        "words": [
            ["lettre", "consultation"],
            ["inivation", "soumissionner"],
            [" dce "],
            ["consultation"],
            ["offre", "financière"],
            ["lc"],
            ["lconsultation"],
        ],
        "stopwords": [],
        "nom_complet": "Lettre de consultation",
        "nom_court": "Lettre consultation",
        "description": (
            "Document invitant des prestataires à candidater (soumissionner) "
            "à un marché public. Lorsque le document vaut pour engagement, "
            "classifier plutôt acte_engagement."
        ),
    },
    "fiche_achat": {
        "words": [],
        "stopwords": [],
        "nom_complet": "Fiche d'achat ou de marché",
        "nom_court": "Fiche d'achat",
        "description": (
            "Fiche d'achat ou de marché servant à préparer la rédaction d'un "
            "marché ou l'émission d'un bon de commande. Les demandes d'achat "
            "sont considérées comme des fiches d'achat."
        ),
    },
    "bon_de_commande": {
        "words": [
            ["bon", "de", "commande"],
            [" bdc "],
            [" bc "],
            ["EXE2"],
            [" bc1"],
            [" bc2"],
            [" bc3"],
            [" bc4"],
            [" bc5"],
            [" bc6"],
            [" bc7"],
            [" bc8"],
            [" bc9"],
            [" bc10"],
        ],
        "stopwords": [],
        "nom_complet": "Bon de commande",
        "nom_court": "Bon de commande",
        "description": (
            "Document administratif émis par l'administration (ou l'acheteur) qui "
            "confirme l'accord de l'achat, généralement sur la base d'un devis ou "
            "d'une proposition commerciale. Peut comprendre les annexes au bon de commande.."
        ),
    },
    "delegation_pouvoir": {
        "words": [["delegation", "signature"], ["pouvoir"]],
        "stopwords": [],
        "nom_complet": "Délégation de pouvoir",
        "nom_court": "Délégation pouvoir",
        "description": "Document permettant de déléguer une signature ou un pouvoir à une autre personne.",
    },
    "rapport_analyse_offre": {
        "words": [["rao"]],
        "stopwords": [],
        "nom_complet": "Rapport d'analyse des offres ou de présentation des offres",
        "nom_court": "Rapport analyse offres",
        "description": (
            "Rapport d'analyse des candidatures de prestataires à un marché public "
            "suite à une consultation aux entreprises. Le document compare l'analyse "
            "des offres reçues dans le cadre d'un marché public. Egalement parfois "
            "appelé rapport de présentation."
        ),
    },
    "abondement": {
        "words": [["abondement"], [" ea "]],
        "stopwords": [],
        "nom_complet": "Abondement",
        "nom_court": "Abondement",
        "description": "Document justifiant une demande d'abondement de crédit.",
    },
    "avis_boamp": {
        "words": [["avis", "boamp"]],
        "stopwords": [],
        "nom_complet": "Avis BOAMP",
        "nom_court": "Avis BOAMP",
        "description": "",
    },
    "sous_traitance": {
        "words": [["sous", "traitance"], ["DC4"]],
        "stopwords": [],
        "nom_complet": "Sous-traitance",
        "nom_court": "Sous-traitance",
        "description": "Formulaire de déclaration de sous-traitance d'un marché public. Souvent formulaire 'DC4'",
    },
    "fiche_communication": {
        "words": [["communication"], ["fcom"]],
        "stopwords": [],
        "nom_complet": "Fiche de communication ou de transmission",
        "nom_court": "Fiche communication",
        "description": (
            "Fiche de communication entre les logiciels PLACE et Chorus. Les fiches "
            "de communication ou fiches Chorussont également des fiches communication."
        ),
    },
    "ej_complexe": {
        "words": [["ej", "complexe"], ["fmec"], ["formulaire", "creation", " ej "]],
        "stopwords": [],
        "nom_complet": "EJ complexe",
        "nom_court": "EJ complexe",
        "description": "Formulaire de déclaration ou création d'un EJ complexe.",
    },
    "question_reponse": {
        "words": [["qr"]],
        "stopwords": [],
        "nom_complet": "Questions/Réponses",
        "nom_court": "Q/R",
        "description": (
            "Document complémentaire à la consultation des entreprises dans le cadre d'un marché "
            "public comprenant les questions et réponses échangées entre les candidats et le "
            "commanditaire."
        ),
    },
    "ordre_service": {
        "words": [["ordre", "service"], ["EXE1"], [" os "], ["affermissement"]],
        "stopwords": [],
        "nom_complet": "Ordre de service",
        "nom_court": "Ordre de service",
        "description": "Formulaire EXE1 permettant le lancement d'une tranche optionnelle d'un marché.",
    },
    "decomposition_prix": {
        "words": [["dgpf"], ["dpgf"], ["révision", "prix"]],
        "stopwords": [["FMEC"]],
        "nom_complet": "Décomposition du prix",
        "nom_court": "Décomposition prix",
        "description": (
            "Document présentant la décomposition du prix d'un achat public. "
            "Souvent appelé Décomposition du prix global forfaitaire."
        ),
    },
    "detail_quantitatif_estimatif": {
        "words": [["detail", "quantitatif", "estimatif"], ["dqe"]],
        "stopwords": [],
        "nom_complet": "Detail quantitatif estimatif",
        "nom_court": "DQE",
        "description": (
            "Document présentant le détail quantitatif estimatif d'un marché public, "
            "donne une idée de la quantité de commande sur l'année."
        ),
    },
    "bordereau_prix": {
        "words": [[" bpu "], [" bp "], ["annexe", "financière"], ["bordereau", "prix"]],
        "stopwords": [],
        "nom_complet": "Bordereau de prix unitaire",
        "nom_court": "BPU",
        "description": (
            "Document récapitulatif des prix unitaires proposés dans le cadre du marché, "
            "aussi annexe financière du marché."
        ),
    },
    "acte_engagement": {
        "words": [[" ae"], ["acte", "engagement"], ["attri1"]],
        "stopwords": [["annexe"]],
        "nom_complet": "Acte d'engagement",
        "nom_court": "Acte d'engagement",
        "description": (
            "Un acte d’engagement est un document contractuel par lequel le titulaire d’un marché "
            "public ou d’un contrat administratif s’engage formellement à exécuter les prestations "
            "prévues, conformément aux conditions définies par l’acheteur, et qui scelle juridiquement "
            "l’accord des parties."
        ),
    },
    "lettre_candidature": {
        "words": [["DC1"], ["lettre", "candidature"]],
        "stopwords": [],
        "nom_complet": "Lettre de candidature",
        "nom_court": "Lettre candidature",
        "description": "Spécifiquement le formulaire DC1",
    },
    "lettre_candidature_2": {
        "words": [["DC2"]],
        "stopwords": [],
        "nom_complet": "Lettre de candidature DC2",
        "nom_court": "Lettre candidature DC2",
        "description": "Spécifiquement le formulaire DC2",
    },
    "fiche_navette": {
        "words": [["navette"], [" fn "], ["fiche", "modificative"], ["fnav"]],
        "stopwords": [],
        "nom_complet": "Fiche navette",
        "nom_court": "Fiche navette",
        "description": (
            "Fiche dite navette entre PLACE et Chorus permettant la transmission "
            "d'informations entre les logiciels. Contient la mention explicite de "
            "'Fiche navette' au début du document."
        ),
    },
    "fiche_modificative": {
        "words": [["fiche", "modificative"]],
        "stopwords": [],
        "nom_complet": "Fiche modificative d'une fiche navette",
        "nom_court": "Fiche modificative",
        "description": (
            "Contient la mention explicite 'Fiche modificative' au début du document. "
            "Fiche de demande de modification, permettant de modifier les informations "
            "dans le logiciel Chorus."
        ),
    },
    "memoire_technique": {
        "words": [["memoire", "technique"], ["proposition", "technique"], ["offre", "technique"]],
        "stopwords": [],
        "nom_complet": "Mémoire technique",
        "nom_court": "Mémoire technique",
        "description": (
            "Proposition technique d'un candidat à un marché. De formes variées, "
            "comprenant le détail des prestations proposées, souvent des références, ..."
        ),
    },
    "fiche_engagement": {
        "words": [["fiche", "engagement"], ["fiche", "transmission", "marché"]],
        "stopwords": [],
        "nom_complet": "Fiche d'engagement",
        "nom_court": "Fiche d'engagement",
        "description": (
            "Fiche interne demandant l'engagement d'une commande auprès d'un "
            "service juridique, marché ou affaires financières."
        ),
    },
    "devis": {
        "words": [["devis"]],
        "stopwords": [],
        "nom_complet": "Devis",
        "nom_court": "Devis",
        "description": (
            "Devis en amont de la commande. Ressemble parfois à une facture, "
            "mais prévisionnelle ou à payer une fois le service réalisé. Les "
            "propositions ou offres commerciales sont également des devis."
        ),
    },
    "cctp": {
        "words": [["cctp"], ["ccp"], ["cahier", "charge"]],
        "stopwords": [["administrat"]],
        "nom_complet": "CCTP (Cahier des Clauses Techniques Particulières)",
        "nom_court": "CCTP",
        "description": "Cahier des charges techniques spécifiant les exigences techniques du marché.",
    },
    "ccap": {
        "words": [["ccap"]],
        "stopwords": [["annexe"], ["notif"]],
        "nom_complet": "CCAP (Cahier des Clauses Administratives Particulières)",
        "nom_court": "CCAP",
        "description": "Cahier des charges administratives spécifiant les exigences administratives du marché.",
    },
    "commentaire": {
        "words": [["comment"]],
        "stopwords": [],
        "nom_complet": "Commentaire",
        "nom_court": "Commentaire",
        "description": "Document spécifique à Chorus coeur, format txt.",
    },
    "facture": {
        "words": [["facture"], [" fac "]],
        "stopwords": [],
        "nom_complet": "Facture",
        "nom_court": "Facture",
        "description": (
            "Document émis par un prestataire à l'administration (ou l'acheteur) "
            "pour facturer un service rendu. Attention, une facture s'adresse à "
            "l'administration, elle ne vient pas de l'administration."
        ),
    },
    "service_fait": {
        "words": [["service", "fait"], [" sf "]],
        "stopwords": [],
        "nom_complet": "Service fait",
        "nom_court": "Service fait",
        "description": "Déclaration de service fait.",
    },
    "avenant": {
        "words": [["avenant"], ["EXE10"], [" avnt"], [" avt "]],
        "stopwords": [["rapport"]],
        "nom_complet": "Avenant",
        "nom_court": "Avenant",
        "description": (
            "Avenant d'un 'Acte d'engagement' (autre document spécifique). "
            "L'avenant a souvent la même forme qu'un acte d'engagement et "
            "comprend 'avenant' dans son titre."
        ),
    },
}


def normalize_text(text):
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.lower()
    text = re.sub(r"[_\-]+", " ", text)  # remplace _ et - par espace
    text = re.sub(r"[^a-z0-9\s]", "", text)  # supprime la ponctuation
    return re.sub(r"\s+", " ", text)  # espaces multiples
