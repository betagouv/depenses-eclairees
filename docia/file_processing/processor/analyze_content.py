"""
Analyse le contexte fourni en utilisant l'api et les modèles d'IA. Prend en entrée un contexte (plus ou moins long)
Contexte = parfois tout le texte extrait, parfois seulement une liste de chunks concaténés.
"""

import logging
import pandas as pd

from ..llm.client import LLMClient
from .attributes_query import ATTRIBUTES, select_attr
from .post_processing_llm import clean_llm_response

logger = logging.getLogger("docia." + __name__)


# Fonction pour générer le prompt à partir des attributs à chercher
def get_prompt_from_attributes(df_attributes: pd.DataFrame):
    question = """Extrait les informations clés et renvoie-les uniquement au format 
        JSON spécifié, sans texte supplémentaire.

        Format de réponse (commence par "{" et termine par "}") :
        {
    """
    for idx, row in df_attributes.iterrows():
        attr = row["attribut"]
        if idx != df_attributes.index[-1]:
            question += f"""  "{attr}": "", \n"""
        else:
            question += f"""  "{attr}": "" \n"""
    question += """}

  Instructions d'extraction :\n\n"""
    for idx, row in df_attributes.iterrows():
        consigne = row["consigne"]
        if idx != df_attributes.index[-1]:
            question += f"""{consigne}\n"""
        else:
            question += f"""{consigne}"""
    return question


def create_response_format(df_attributes, classification):
    df_filtered = select_attr(df_attributes, classification)

    # Schéma par défaut : type string
    default_schema = {"type": ["string", "null"]}

    # Construire le dictionnaire des propriétés avec les schémas appropriés
    properties = {}
    l_output_field = []

    for idx, row in df_filtered.iterrows():
        output_field = row["output_field"]
        l_output_field.append(output_field)

        # Par défaut, utiliser le schéma string
        schema_to_use = default_schema

        # Si la colonne 'schema' existe et contient une valeur valide
        if "schema" in df_filtered.columns:
            schema_value = row.get("schema")

            if schema_value:
                if not isinstance(schema_value, dict):
                    raise ValueError(f"Schema must be a dict (field={output_field})")
                schema_to_use = schema_value

        properties[output_field] = schema_to_use

    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": f"{classification}",
            "schema": {"type": "object", "properties": properties, "required": l_output_field},
        },
    }
    return response_format


def analyze_file_text(text: str, document_type: str, llm_model: str = "openweight-medium", temperature: float = 0.0):
    """
    Analyse le texte pour extraire des informations.

    Args:
        text: Texte à analyser
        response_format: Format de réponse à utiliser
        temperature: Température pour la génération (0.0 = déterministe)

    Returns:
        Réponse du LLM à la question posée
    """

    response = analyze_file_text_llm(text, document_type, llm_model, temperature)
    data = clean_llm_response(document_type, response)

    return {
        "llm_response": response,
        "structured_data": data,
    }


def analyze_file_text_llm(
    text: str, document_type: str, llm_model: str = "openweight-medium", temperature: float = 0.0
):
    llm_env = LLMClient()

    question = get_prompt_from_attributes(select_attr(ATTRIBUTES, document_type))
    response_format = create_response_format(ATTRIBUTES, document_type)

    if not text:
        raise ValueError("Le texte est vide.")

    system_prompt = "Vous êtes un assistant IA qui analyse des documents juridiques."
    user_prompt = f"Analyse le contexte suivant et réponds à la question : {question}\n\nContexte : {text}"

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    response = llm_env.ask_llm(messages, model=llm_model, response_format=response_format, temperature=temperature)

    return response
