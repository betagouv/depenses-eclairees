"""
Analyse le contexte fourni en utilisant l'api et les modèles d'IA. Prend en entrée un contexte (plus ou moins long)
Contexte = parfois tout le texte extrait, parfois seulement une liste de chunks concaténés.
"""
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from ..llm.client import LLMClient
from .attributes_query import select_attr, ATTRIBUTES
from .post_processing_llm import clean_llm_response

logger = logging.getLogger("docia." + __name__)


# Fonction pour générer le prompt à partir des attributs à chercher
def get_prompt_from_attributes(df_attributes: pd.DataFrame ):
  question = """Extrait les informations clés et renvoie-les uniquement au format JSON spécifié, sans texte supplémentaire.

  Format de réponse (commence par "{" et termine par "}") :
{
"""
  for idx, row in df_attributes.iterrows():
      attr = row["attribut"]
      if idx != df_attributes.index[-1]:
        question+=f"""  "{attr}": "", \n"""
      else:
        question+=f"""  "{attr}": "" \n""" 
  question+="""}

  Instructions d'extraction :\n\n"""    
  for idx, row in df_attributes.iterrows():
      consigne = row["consigne"]
      if idx != df_attributes.index[-1]:
        question+=f"""{consigne}\n"""
      else:
        question+=f"""{consigne}"""
  return question

def create_response_format(df_attributes, classification):
    df_filtered = select_attr(df_attributes, classification)
    
    # Schéma par défaut : type string
    default_schema = {"type": "string"}
    
    # Construire le dictionnaire des propriétés avec les schémas appropriés
    properties = {}
    l_output_field = []
    
    for idx, row in df_filtered.iterrows():
        output_field = row['output_field']
        l_output_field.append(output_field)
        
        # Par défaut, utiliser le schéma string
        schema_to_use = default_schema
        
        # Si la colonne 'schema' existe et contient une valeur valide
        if 'schema' in df_filtered.columns:
            schema_value = row.get('schema')
            
            if schema_value:
                if not isinstance(schema_value, dict):  
                    raise ValueError(f"Schema must be a dict (field={output_field})")  
                schema_to_use = schema_value

        properties[output_field] = schema_to_use
    
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": f"{classification}",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": l_output_field
            }
        }
    }
    return response_format


def df_analyze_content(df: pd.DataFrame,
                       df_attributes: pd.DataFrame,
                       llm_model: str|None = None,
                       temperature: float = 0.0, 
                       max_workers: int = 4) -> pd.DataFrame:
    """
    Analyse le contenu d'un DataFrame en parallèle en utilisant l'API LLM.

    Returns:
        DataFrame avec les réponses du LLM ajoutées
    """
    dfResult = df.copy()
    dfResult['llm_response'] = None
    dfResult['structured_data'] = None

    for attr in df_attributes.attribut:
        dfResult[attr] = None

    # Fonction pour traiter une ligne
    def process_row(idx):
        row = df.loc[idx]
        classification = row['classification']
        kwargs = dict(
            text=row["relevant_content"] or row["text"],
            document_type=classification,
            temperature=temperature
        )
        if llm_model:
            kwargs["llm_model"] = llm_model
        try:
            result = analyze_file_text(**kwargs)
            result["error"] = None
        except Exception as e:
            result = {
                'llm_response': None,
                'structured_data': None,
                'error': f"Erreur lors de l'analyse: {str(e)}"
            }
            logger.exception(f"Erreur lors de l'analyse du fichier {row['filename']}: {e}")

        if not result["error"]:
            for attr in df_attributes.attribut:
                result.update({f'{attr}': result["llm_response"].get(attr, '')})
        else:
            logger.error(f"Erreur lors de l'analyse du fichier {row["filename"]}: {result['error']}")

        return idx, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_row, i) for i in df.index]
        
        for future in tqdm(futures, total=len(futures), desc="Traitement des PJ"):
            idx, result = future.result()
            for key, value in result.items():
                dfResult.at[idx, key] = value

    return dfResult


def analyze_file_text(text: str, document_type: str, llm_model: str = 'openweight-medium', temperature: float = 0.0):
    """
    Analyse le texte pour extraire des informations.

    Args:
        text: Texte à analyser
        df_attributes: Question à poser au LLM
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


def analyze_file_text_llm(text: str, document_type: str, llm_model: str = 'openweight-medium', temperature: float = 0.0):

    llm_env = LLMClient(llm_model)

    question = get_prompt_from_attributes(select_attr(ATTRIBUTES, document_type))
    response_format = create_response_format(ATTRIBUTES, document_type)

    if not text:
        raise ValueError("Le texte est vide.")

    system_prompt = "Vous êtes un assistant IA qui analyse des documents juridiques."
    user_prompt = f"Analyse le contexte suivant et réponds à la question : {question}\n\nContexte : {text}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = llm_env.ask_llm(messages, response_format, temperature)

    return response
