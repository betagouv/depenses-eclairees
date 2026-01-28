from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import requests
import pandas as pd

from app import processor
from app import grist
from app.data.sql.sql import bulk_update_engagements, select_engagements_with_attachments

from app.grist import URL_TABLE_ENGAGEMENTS, URL_TABLE_ATTACHMENTS, API_KEY_GRIST
from app.ai_models.config_albert import ALBERT_API_KEY, ALBERT_BASE_URL
from app.utils import log_execution_time


def get_useful_infos_from_docs(df_docs_EJ):
    """
    Génère un texte contenant les informations utiles à partir des documents analysés d'un EJ.
    Un document pertinent a un champ 'text' non vide.

    Args:
        df_docs (pd.DataFrame): DataFrame des documents liés à un num_EJ

    Returns:
        str: prompt à envoyer au LLM
    """
    # Filtrer les documents pertinents
    docs_pertinents = df_docs_EJ[
        (df_docs_EJ["text"].astype(str).str.strip() != "")
    ]

    if docs_pertinents.empty:
        return "Aucun document pertinent trouvé pour ce numéro d'EJ."

    prompt_lines = ["Documents pertinents pour ce numéro d'EJ :\n"]
    for _, row in docs_pertinents.iterrows():
        prompt_lines.append(
            f"- {row['filename']} | Classification : {row['classification']}\n\n Infos extraites : {row['llm_response']}\n"
        )
    return "\n".join(prompt_lines)


# prompt = """
# Tu es un analyste de marchés publics.  
# Je vais te fournir une liste de documents. Chaque document est décrit par :  
# - son nom de fichier,  
# - sa classification (ex. acte d’engagement, avenant, fiche navette, etc.),  
# - un JSON des informations extraites.  

# Ta mission :  
# Produire une synthèse consolidée des informations suivantes :  
# 1. "libelle" : libellé de la prestation synthétique (formulation consolidée et résumé clair des prestations).
# 2. "description_detaillee" : Description détaillée des prestations le plus complet et exhaustif possible (max 1000 caractères).
# 3. "administration_beneficiaire" : Administration bénéficiaire ou acheteuse (si possible en précisant les différents niveaux de directions, par exemple Ministère > Direction > Service > ...).
# 4. "prestataire" : Prestataire principal (société titulaire du marché).  
# 5. "siret_prestataire" : SIRET du prestataire principal (société titulaire du marché).  
# 6. "date_prestation" : Date de réalisation de la prestation (signature, édition, avenants, etc.), au format jj/mm/aaaa. Une seule date !

# Règles de consolidation :
# - Pour chaque champ ci-dessus, si un document contient une information source de ce champ, le document doit être cité dans les sources ou dans les conflits.
# - Tolérance : les petites différences de formulation (syntaxe, majuscules, abréviations, légères différences) ne sont pas considérées comme des conflits, mais comme des compléments ou des variantes compatibles.  
# - Contradictions réelles : si deux documents donnent des informations substantiellement différentes, indique-les dans "conflits".  
# - Priorité des sources en cas de conflit réel :  
#   1. Acte d’engagement  
#   2. Avenant  
#   3. Fiche navette  
# - Sources : toujours lister les documents d'où vient l'information, au format {"filename": "nom_fichier1.pdf", "classification": "..."}.  
# - Si une information est absente ou incomplète, indiquer null pour valeur. 

# Format de sortie attendu (uniquement format Json, aucune phrase hors du JSON), la réponse commence par '{' et finit par '}' :  
# - Pour chaque champ ci-dessus, renvoie la valeur, les sources et les conflits.
# - Voici les formats :
#   * valeur : format texte
#   * sources : liste de {"filename": "nom_fichier1.pdf", "classification": "..."}
#   * conflits : liste de {"source": {"filename": "nom_fichier3.pdf", "classification": "..."}, "valeur": "..."}
  

# Rappels :  
# - Si aucune divergence → "conflits": {} (objet vide).  
# - Toujours respecter strictement ce format JSON.  
# - La sortie finale doit être uniquement le JSON, sans texte d’introduction ou de conclusion.  
# - Ne commence pas ta réponse par "```json" mais par une accolade ouvrante
# """

def get_prompt_for_final_infos_by_field(field):
    if field == "libelle":
        description = """
        - "libelle" : libellé de la prestation synthétique (formulation consolidée et résumé clair des prestations).
        """
    elif field == "description_detaillee":
        description = """
        - "description_detaillee" : Description détaillée des prestations le plus complet et exhaustif possible (max 1000 caractères).
        """
    elif field == "administration_beneficiaire":
        description = """
        - "administration_beneficiaire" : Administration bénéficiaire ou acheteuse (si possible en précisant les différents niveaux de directions, par exemple Ministère > Direction > Service > ...).
        """
    elif field == "prestataire":
        description = """
        - "prestataire" : Prestataire principal (société titulaire du marché).  
        """
    elif field == "siret_prestataire":
        description = """
        - "siret_prestataire" : SIRET du prestataire principal (société titulaire du marché).  
        """
    elif field == "date_prestation":
        description = """
        - "date_prestation" : Date de réalisation de la prestation (signature, édition, avenants, etc.), au format jj/mm/aaaa. Une seule date !
        """

    prompt = f"""
    Tu es un analyste de marchés publics.  
    Je vais te fournir une liste de documents. Chaque document est décrit par :  
    - son nom de fichier,  
    - sa classification (ex. acte d’engagement, avenant, fiche navette, etc.),  
    - un JSON des informations extraites.  

    Ta mission :  
    Produire une synthèse consolidée du champ suivant :  
    {description}
    """
    prompt += """
    Règles de consolidation :
    - Si un document contient une information source de ce champ, le document doit être cité dans les sources ou dans les conflits.
    - Tolérance : les petites différences de formulation (syntaxe, majuscules, abréviations, légères différences) ne sont pas considérées comme des conflits, mais comme des compléments ou des variantes compatibles.  
    - Contradictions réelles : si deux documents donnent des informations substantiellement différentes, indique-les dans "conflits".  
    - Priorité des sources en cas de conflit réel :  
    1. Acte d’engagement  
    2. Avenant  
    3. Fiche navette  
    - Sources : toujours lister les documents d'où vient l'information, au format {"filename": "nom_fichier1.pdf", "classification": "..."}.  
    - Si une information est absente ou incomplète, indiquer null pour valeur. 

    Format de sortie attendu (uniquement format Json, aucune phrase hors du JSON), la réponse commence par '{' et finit par '}' :  
    * valeur : "valeur" : format texte
    * sources : liste de {"filename": "nom_fichier1.pdf", "classification": "..."}
    * conflits : liste de {"source": {"filename": "nom_fichier3.pdf", "classification": "..."}, "valeur": "..."}
    
    Rappels :  
    - Si aucune divergence → "conflits": {} (objet vide).  
    - Toujours respecter strictement ce format JSON.  
    - La sortie finale doit être uniquement le JSON, sans texte d’introduction ou de conclusion.  
    - Ne commence pas ta réponse par "```json" mais par une accolade ouvrante
    """
    return prompt
# {
#   "libelle_prestation": {
#     "valeur": "...",
#     "sources": [
#       {"filename": "nom_fichier1.pdf", "classification": "..."},
#       {"filename": "nom_fichier2.pdf", "classification": "..."}
#     ],
#     "conflits": [
#       {"source": {"filename": "nom_fichier3.pdf", "classification": "..."}, "valeur": "..."},
#       {"source": {"filename": "nom_fichier4.pdf", "classification": "..."}, "valeur": "..."}
#     ]
#   },
#   "description_detaillee": {
#     "valeur": "...",
#     "sources": [
#       {"filename": "nom_fichier1.pdf", "classification": "..."}
#     ],
#     "conflits": [...]
#   },
#   "administration_beneficiaire": {
#     "valeur": "...",
#     "sources": [
#       {"filename": "nom_fichier1.pdf", "classification": "..."}
#     ],
#     "conflits": [
#       {"source": {"filename": "nom_fichier2.pdf", "classification": "..."}, "valeur": "..."}
#     ]
#   },
#   "prestataire": {
#     "valeur": "...",
#     "sources": [
#       {"filename": "nom_fichier1.pdf", "classification": "..."}
#     ],
#     "conflits": [
#       {"source": {"filename": "nom_fichier2.pdf", "classification": "..."}, "valeur": "..."}
#     ]
#   },
#   "siret_prestataire": {
#     "valeur": "...",
#     "sources": [
#       {"filename": "nom_fichier1.pdf", "classification": "..."}
#     ],
#     "conflits": []
#   },
#   "date_prestation": {
#     "valeur": "jj/mm/aaaa",
#     "sources": [
#       {"filename": "nom_fichier1.pdf", "classification": "..."}
#     ],
#     "conflits": [
#       {"source": {"filename": "nom_fichier2.pdf", "classification": "..."}, "valeur": "..."}
#     ]
#   }
# }

# Rappels :  
# - Si aucune divergence → "conflits": {} (objet vide).  
# - Toujours respecter strictement ce format JSON.  
# - La sortie finale doit être uniquement le JSON, sans texte d’introduction ou de conclusion.  
# - Ne commence pas ta réponse par "```json" mais par "{"

def get_prompt_for_final_infos(useful_infos, field):
    return get_prompt_for_final_infos_by_field(field) + useful_infos


def final_infos_for_EJ(num_EJ, llm_env, dfDocs: pd.DataFrame = None):
    if(dfDocs is None):
        print('Extract from grist')
        dfDocs = grist.select_records_by_key([num_EJ],
                                             'num_EJ',
                                             table_url=URL_TABLE_ATTACHMENTS,
                                             api_key=API_KEY_GRIST)

    useful_infos = get_useful_infos_from_docs(dfDocs)
    l_attr = ["libelle", "description_detaillee", "administration_beneficiaire", "prestataire", "siret_prestataire", "date_prestation"]
    final_infos = {}
    final_infos["source_et_conflits"] = {}

    def process_field(field):
        final_info = {}
        final_info[field] = {}
        final_info["source_et_conflits"] = {}
        messages = [
            {"role": "system", "content": "Tu es un analyste de marchés publics."},
            {"role": "user", "content": get_prompt_for_final_infos(useful_infos, field)}
        ]
        response = llm_env.ask_llm(messages)
        try:
            infos, error = processor.parse_json_response(response)
            if infos is not None and field in infos:
                if isinstance(infos.get(field, {}), dict):
                    final_info[field] = infos.get(field, {}).get("valeur", {})
                    final_info["source_et_conflits"] = infos.get(field, {})
                else:
                    final_info[field] = infos.get(field, {})
                    final_info["source_et_conflits"] = infos
                # infos["valeur"] = infos.get(field, {})
                # infos.pop(field, None)
            elif infos is not None and "valeur" in infos:
                final_info[field] = infos.get("valeur", {})
                final_info["source_et_conflits"] = infos
            else:
                final_info[field] = ""
                final_info["source_et_conflits"] = {}
        except Exception as e:
            print("Erreur lors de l'analyse de la réponse JSON :", e)
            print(response)
            final_info[field] = ""
            final_info["source_et_conflits"][field] = {}
        return field, final_info
    with ThreadPoolExecutor(max_workers=len(l_attr)) as executor:
        futures = {executor.submit(process_field, field): field for field in l_attr}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Traitement des champs"):
            try:
                field, result = future.result()
                final_infos[field] = result.get(field, {})
                final_infos["source_et_conflits"][field] = result.get("source_et_conflits", {})
            except Exception as e:
                print("Erreur lors de la sauvegarde du champ :", e)
    return final_infos


def extract_main_fields(infos):
    # Extraction robuste, retourne "" si le champ ou la clé "valeur" est absent
    def safe_get(dict, key):
        try:
            return dict.get(key, {}).get("valeur")
        except Exception as e:
            return ""
        
    return {
        "Designation": safe_get(infos, "libelle"),
        "Descriptif_prestations": safe_get(infos, "description_detaillee"),
        "Date": safe_get(infos, "date_prestation"),
        "Prestataire": safe_get(infos, "prestataire"),
        "SIRET": safe_get(infos, "siret_prestataire"),
        "Administration": safe_get(infos, "administration_beneficiaire")
    }  

def final_infos_all_EJ(dfEJPJ, api_url, api_key, llm_model='albert-large', max_workers=20, save_grist=False):
    """
    Exécute final_infos_for_EJ en parallèle pour chaque EJ et stocke les résultats dans Grist au fur et à mesure.
    Args:
        dfEJPJ (pd.DataFrame): DataFrame contenant les numéros d'EJ (colonne 'engagements.num_EJ') et les données des pièces jointes
        api_url (str): URL de la table Grist pour les records
        api_key (str): Clé API Grist
        llm_model (str): Nom du modèle LLM à utiliser
        max_workers (int): Nombre de threads parallèles
    """

    llm_env = processor.LLMClient(
        api_key=api_key,
        base_url=api_url,
        llm_model=llm_model
    )

    dfResult = dfEJPJ[[col for col in dfEJPJ.columns if "engagements" in col]].copy(deep=False).drop_duplicates('engagements.num_EJ').reset_index(drop=True)
    dfResult.columns = [col.replace("engagements.", "") for col in dfResult.columns]
    if 'attachments.llm_response' not in dfEJPJ.columns:
        print('Extract from Scalingo')
        list_cat = ["devis", "fiche_navette", "acte_engagement", "bon_de_commande", "avenant"]
        dfDocs = select_engagements_with_attachments(list_cat=list_cat)
    dfDocs = dfEJPJ[["engagements.num_EJ"] + [col for col in dfEJPJ.columns if "attachments" in col]]
    dfDocs.columns = [col.replace("attachments.", "").replace("engagements.", "") for col in dfDocs.columns]

    def process_row(idx):
        num_EJ = dfResult.loc[idx, 'num_EJ']

        # Si dfDocs est fourni, on utilise les PJ pour les informations de synthèse, sinon, on fait appel à Scalingo.
        dfDocsEJ = dfDocs[dfDocs['num_EJ'] == num_EJ]

        with log_execution_time(f"final_infos_for_EJ({num_EJ})"):
            infos = final_infos_for_EJ(num_EJ, llm_env, dfDocsEJ)
            # main_fields = extract_main_fields(infos)

        # Construire un dictionnaire avec les champs principaux et la synthèse complète
        return idx, {
            "Designation": infos.get("libelle", {}),  
            "Descriptif_prestations": infos.get("description_detaillee", {}),
            "Date": infos.get("date_prestation", {}),
            "Prestataire": infos.get("prestataire", {}),
            "SIRET": infos.get("siret_prestataire", {}),
            "Administration": infos.get("administration_beneficiaire", {}),
            "Sources_et_conflits": json.dumps(infos.get("source_et_conflits", {}), ensure_ascii=False)
        }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_row, idx): idx for idx in dfResult.index}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Traitement des EJ"):
            idx, result = future.result()
            
            for key, value in result.items():
                dfResult.at[idx, key] = value

    try:
        if(save_grist):
            grist.update_records_in_grist(dfResult, 
                              key_column='num_EJ', 
                              table_url=URL_TABLE_ENGAGEMENTS,
                              api_key=API_KEY_GRIST,
                              columns_to_update=['Designation', 'Descriptif_prestations','Date', 'Prestataire','SIRET', "Administration", "Sources_et_conflits"])

    except Exception as e:
        print(f"Erreur lors de la sauvegarde du DataFrame : {e}")

    return dfResult


def save_final_infos_all_EJ_result(df: pd.DataFrame):
    columns = ['Designation', 'Descriptif_prestations',
               'Date', 'Prestataire', 'SIRET', "Administration",
               "Sources_et_conflits"]
    bulk_update_engagements(df, columns)