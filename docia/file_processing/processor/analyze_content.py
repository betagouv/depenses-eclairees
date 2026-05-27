"""
Analyse le contexte fourni en utilisant l'api et les modèles d'IA. Prend en entrée un contexte (plus ou moins long)
Contexte = parfois tout le texte extrait, parfois seulement une liste de chunks concaténés.
"""

import logging
from dataclasses import dataclass

from ..llm.client import LLMClient, LLMUsage
from .attributes_query import DOC_TYPE_ATTRIBUTES_MAPPING, DOC_TYPE_SCHEMA_MAPPING
from .constants import DEFAULT_ANALYZE_MODEL
from .post_processing_llm import clean_llm_response

logger = logging.getLogger("docia." + __name__)


@dataclass
class AnalyzeResult:
    llm_response: dict
    structured_data: dict
    model: str | None
    usage: LLMUsage


# Fonction pour générer le prompt à partir des attributs à chercher
def get_question(doc_attributes):
    question = """Extrait les informations clés et renvoie-les uniquement au format 
        JSON spécifié, sans texte supplémentaire.

        Format de réponse (commence par "{" et termine par "}") :
        {
    """
    for attr in doc_attributes.keys():
        question += f"""  "{attr}": "",\n"""
    question += """}

  Instructions d'extraction :\n\n"""
    for attribute_key, attribute_definition in doc_attributes.items():
        consigne = attribute_definition["consigne"]
        question += f"""{attribute_key.upper()}\n{consigne}\n\n"""
    return question


def create_response_format(doc_schema, classification):
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"{classification}",
            "strict": True,
            "schema": doc_schema,
        },
    }


def analyze_file_text(
    text: str, document_type: str, llm_model: str = DEFAULT_ANALYZE_MODEL, temperature: float = 0.0
) -> AnalyzeResult:
    """
    Analyse le texte pour extraire des informations.

    Args:
        text: Texte à analyser
        response_format: Format de réponse à utiliser
        temperature: Température pour la génération (0.0 = déterministe)

    Returns:
        Réponse du LLM à la question posée
    """

    response, usage = analyze_file_text_llm(text, document_type, llm_model, temperature)
    data = clean_llm_response(document_type, response)

    return AnalyzeResult(
        llm_response=response,
        structured_data=data,
        usage=usage,
        model=llm_model,
    )


def analyze_file_text_llm(
    text: str, document_type: str, llm_model: str = "mistral-medium-2508", temperature: float = 0.0
) -> tuple[dict, LLMUsage]:
    llm_env = LLMClient()

    question = get_question(DOC_TYPE_ATTRIBUTES_MAPPING[document_type])
    response_format = create_response_format(DOC_TYPE_SCHEMA_MAPPING[document_type], document_type)

    if not text:
        raise ValueError("Le texte est vide.")

    system_prompt = "Vous êtes un assistant IA qui analyse des documents juridiques."
    user_prompt = f"Analyse le contexte suivant et réponds à la question : {question}\n\nContexte : {text}"

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    response = llm_env.ask_llm(messages, model=llm_model, response_format=response_format, temperature=temperature)

    # Force typing to dict
    dict_content: dict = response.content

    return dict_content, response.usage
