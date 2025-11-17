"""
Analyse le contexte fourni en utilisant l'api et les modèles d'IA. Prend en entrée un contexte (plus ou moins long)
Contexte = parfois tout le texte extrait, parfois seulement une liste de chunks concaténés.
"""


import pandas as pd
import json
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from openai import OpenAI, RateLimitError
from typing import List, Dict, Tuple, Optional, Union, Any

from app.ai_models.config_albert import BASE_URL_PROD, API_KEY_AMA
from .attributes_query import select_attr
from app.utils import getDate, log_execution_time
from app.grist import update_records_in_grist
from app.grist import API_KEY_GRIST, URL_TABLE_ATTACHMENTS
from ..data.sql.sql import bulk_update_attachments

logger = logging.getLogger("docia." + __name__)

class LLMEnvironment:

# init
    def __init__(
        self, 
        api_key: str,
        base_url: Optional[str] = None,
        llm_model: str = "neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8",
    ):
        """
        Initialise l'environnement RAG.
        
        Args:
            api_key: Clé API OpenAI
            base_url: URL de base pour l'API OpenAI (facultatif)
            embedding_model: Modèle d'embedding à utiliser
            llm_model: Modèle LLM à utiliser
            chunk_size: Taille des chunks en caractères
            chunk_overlap: Chevauchement entre les chunks en caractères
            embedding_dimension: Dimension des vecteurs d'embedding
            hybrid_search: Activer la recherche hybride (sémantique + lexicale)
            semantic_weight: Poids de la recherche sémantique (0 à 1)
            retrieval_top_k: Nombre de chunks à récupérer lors de la recherche
        """
        self.api_key = api_key
        self.base_url = base_url
        self.llm_model = llm_model

        # Initialisation du client OpenAI
        self.client = self._initialize_openai_client()
           
    # API LLM à remplacer par un appel à une fonction dédiée
    def _initialize_openai_client(self) -> OpenAI:
        """
        Initialise le client OpenAI avec la clé API fournie et éventuellement une URL de base personnalisée.
        
        Returns:
            Instance du client OpenAI
        """
        client_kwargs = {"api_key": self.api_key}
        
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
            
        return OpenAI(**client_kwargs)

    def ask_llm(
        self, 
        message: dict, 
        response_format: dict = None, 
        temperature: float = 0.0, 
        max_retries: int = 6, 
        retry_delay: float = 5.0
    ) -> str:
        """
        Interroge le LLM avec un prompt système et utilisateur.
        En cas d'erreur de rate limiting (429), attend et réessaye automatiquement.
        
        Args:
            message:
                system_prompt: Prompt système pour définir le rôle du LLM
                user_prompt: Prompt utilisateur avec la question
            response_format: Format de réponse à utiliser
            temperature: Température pour la génération (0.0 = déterministe)
            max_retries: Nombre maximum de tentatives en cas d'erreur 429 (défaut: 3)
            retry_delay: Délai d'attente en secondes entre les tentatives (défaut: 2.0)
            
        Returns:
            Réponse du LLM
            
        Raises:
            Exception: Si toutes les tentatives échouent ou si l'erreur n'est pas de type 429
        """
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=message,
                    temperature=temperature,
                    response_format=response_format if response_format else None
                )

                content = response.choices[0].message.content.strip()

                return content  # Succès

            except RateLimitError as e:
                # Cas proxy : l'API retourne une "réponse d'erreur" au lieu d'une exception
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    logger.warning(f"Erreur 429 - RateLimitError détectée, retry dans {wait_time:.1f}s (tentative {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue  # Réessaye
                else:
                    raise
            
    def analyze_content(self, context: str, question: str, response_format: dict = None, temperature: float = 0.0) -> str:
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
        system_prompt = "Vous êtes un assistant IA qui analyse des documents juridiques."
        user_prompt = f"Analyse le contexte suivant et réponds à la question : {question}\n\nContexte : {context}"
        
        message = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self.ask_llm(message, response_format, temperature)

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
    except Exception as e:
        return None, f"Erreur d'analyse: {str(e)}"
    
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

    llm_env = LLMEnvironment(
        api_key=api_key,
        base_url=base_url,
        llm_model=llm_model
    )
    
    # Fonction pour traiter une ligne
    def process_row(idx):
        row = df.loc[idx]
        classification = row['classification']
        try:
            question = get_prompt_from_attributes(select_attr(df_attributes, classification))
            response_format = create_response_format(df_attributes, classification)
            context = row['relevant_content']

            if(context == ""):
                raise ValueError("Le contexte est vide.")

            with log_execution_time(f"df_analyze_content({row.filename})"):
                response = llm_env.analyze_content(context=context,
                                                question=question,
                                                response_format=response_format,
                                                temperature=temperature)
            data, error = parse_json_response(response)

            result = {
                'llm_response': json.dumps(data),
                'json_error': error
            }

            if not error:
                for attr in df_attributes.attribut:
                    result.update({f'{attr}': data.get(attr, '')})
            else: 
                print(f"Erreur lors de l'analyse du fichier {row["filename"]}: {error}")
        except Exception as e:
            result = {
                'llm_response': None,
                'json_error': f"Erreur lors de l'analyse: {str(e)}"
            }
            print(f"Erreur lors de l'analyse du fichier {row['filename']}: {e}")

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

def save_df_analyze_content_result(df: pd.DataFrame):
    bulk_update_attachments(df, ['llm_response', 'json_error'])

