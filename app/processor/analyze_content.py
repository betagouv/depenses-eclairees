"""
Analyse le contexte fourni en utilisant l'api et les modèles d'IA. Prend en entrée un contexte (plus ou moins long)
Contexte = parfois tout le texte extrait, parfois seulement une liste de chunks concaténés.
"""

import pandas as pd
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from docia.file_processing.llm import LLMClient
from .attributes_query import select_attr
from app.utils import getDate
from app.grist import update_records_in_grist
from app.grist import API_KEY_GRIST, URL_TABLE_ATTACHMENTS
from ..data.sql.sql import bulk_update_attachments

logger = logging.getLogger("docia." + __name__)


# Fonction pour extraire le JSON de la réponse
def parse_json_response(response_text):
    try:
        # Recherche d'un objet JSON dans la réponse
        json_pattern = r'(\{.*\})'
        json_matches = re.search(json_pattern, response_text, re.DOTALL)

        if json_matches:
            json_str = json_matches.group(1)
            # Analyse du JSON
            data = json.loads(json_str)
            return data, None
        else:
            return None, "Aucun JSON trouvé dans la réponse"
    except json.JSONDecodeError as e:
        return None, f"Format JSON invalide: {str(e)}"


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
    l_output_field = select_attr(df_attributes, classification).output_field.tolist()
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": f"{classification}",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {output_field: {"type": "string"} for output_field in l_output_field},
                "required": list(df_attributes.output_field)
            }
        }
    }
    return response_format

def df_analyze_content(api_key, 
                       base_url, 
                       llm_model, 
                       df: pd.DataFrame, 
                       df_attributes: pd.DataFrame, 
                       temperature: float = 0.0, 
                       max_workers: int = 4, 
                       save_path: str = None, 
                       directory_path: str = None,
                       save_grist: bool = False) -> pd.DataFrame:
    """
    Analyse le contenu d'un DataFrame en parallèle en utilisant l'API LLM.
    
    Args:
        df: DataFrame contenant les textes à analyser
        question: Question à poser au LLM pour chaque texte
        temperature: Température pour la génération (0.0 = déterministe)
        max_workers: Nombre maximum de threads pour l'exécution parallèle
        
    Returns:
        DataFrame avec les réponses du LLM ajoutées
    """
    dfResult = df.copy()
    dfResult['llm_response'] = None
    dfResult['json_error'] = None

    for attr in df_attributes.attribut:
        dfResult[attr] = None

    # Fonction pour traiter une ligne
    def process_row(idx):
        row = df.loc[idx]
        classification = row['classification']
        try:
            result = analyze_file_text(row["filename"], row["relevant_content"] or row["text"],
                                       df_attributes, classification,
                                       llm_model=llm_model, temperature=temperature)
        except Exception as e:
            result = {
                'llm_response': None,
                'json_error': f"Erreur lors de l'analyse: {str(e)}"
            }
            print(f"Erreur lors de l'analyse du fichier {row['filename']}: {e}")

        if not result["json_error"]:
            for attr in df_attributes.attribut:
                result.update({f'{attr}': result["llm_response"].get(attr, '')})
        else:
            print(f"Erreur lors de l'analyse du fichier {row["filename"]}: {result['json_error']}")

        return idx, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_row, i) for i in df.index]
        
        for future in tqdm(futures, total=len(futures), desc="Traitement des PJ"):
            idx, result = future.result()
            for key, value in result.items():
                dfResult.at[idx, key] = value
                
    try:
        if(save_grist):
            update_records_in_grist(dfResult, 
                              key_column='filename', 
                              table_url=URL_TABLE_ATTACHMENTS,
                              api_key=API_KEY_GRIST,
                              columns_to_update=['llm_response', 'json_error'])

        if(save_path != None and directory_path != None):
                dfResult.to_csv(f'{save_path}/contentanalyzed_{directory_path.split("/")[-1]}_{getDate()}.csv', index = False)
                print(f"Liste des fichiers sauvegardées dans {save_path}/contentanalyzed_{directory_path.split("/")[-1]}_{getDate()}.csv")
    
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des fichiers : {e}")

    return dfResult


def analyze_file_text(filename: str, text: str, df_attributes: pd.DataFrame, classification: str, llm_model: str = 'albert-large', temperature: float = 0.0):
    """
    Analyse le contexte fourni en utilisant l'API LLM.

    Args:
        context: Contexte à analyser (texte complet ou liste de chunks)
        question: Question à poser au LLM
        response_format: Format de réponse à utiliser
        temperature: Température pour la génération (0.0 = déterministe)

    Returns:
        Réponse du LLM à la question posée
    """

    llm_env = LLMClient(llm_model)

    question = get_prompt_from_attributes(select_attr(df_attributes, classification))
    response_format = create_response_format(df_attributes, classification)

    if not text:
        raise ValueError("Le contexte est vide.")

    system_prompt = "Vous êtes un assistant IA qui analyse des documents juridiques."
    user_prompt = f"Analyse le contexte suivant et réponds à la question : {question}\n\nContexte : {text}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = llm_env.ask_llm(messages, response_format, temperature)

    data, error = parse_json_response(response)

    result = {
        'llm_response': data,
        'json_error': error
    }
    return result


def save_df_analyze_content_result(df: pd.DataFrame):
    bulk_update_attachments(df, ['llm_response', 'json_error'])

