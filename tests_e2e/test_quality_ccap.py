import json
import re
import pandas as pd
import pytest
import logging
from datetime import datetime
import copy

import sys
sys.path.append(".")

from django.conf import settings

from app.processor.analyze_content import df_analyze_content, LLMClient, parse_json_response
from app.processor.attributes_query import ATTRIBUTES
from app.ai_models.config_albert import ALBERT_API_KEY, ALBERT_BASE_URL
from app.processor.post_processing_llm import *

logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()


def normalize_string(s):
    """Normalise une chaîne de caractères : minuscule et sans caractères spéciaux."""
    if pd.isna(s) or s == "":
        return ""
    s = str(s).lower()
    # Supprime les caractères spéciaux (garde seulement les lettres, chiffres et espaces)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    # Supprime les espaces multiples
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def compare_contract_object(llm_val, ref_val, llm_model='albert-small'):
    """Compare l'objet du marché CCAP."""
    if llm_val == '' and ref_val == '':
        return True
    if llm_val == '' or ref_val == '':
        return False
    
    try:
        llm_env = LLMClient(api_key=ALBERT_API_KEY, base_url=ALBERT_BASE_URL, llm_model=llm_model)
        system_prompt = "Vous êtes un expert en analyse sémantique de documents juridiques. Votre rôle est d'évaluer la proximité de sens entre deux descriptions d'objets."
        user_prompt = f"""Compare les deux descriptions d'objet de marché suivantes et détermine si elles décrivent la même chose.

    Valeur extraite par le LLM: {llm_val}
    Valeur de référence: {ref_val}

    Réponds UNIQUEMENT avec un JSON valide:
    {{
        "sont_proches": true ou false,
        "explication": "brève explication"
    }}"""
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        response = llm_env.ask_llm(messages=messages, response_format={"type": "json_object"}, temperature=0.2)
        result, error = parse_json_response(response)
        if error:
            logger.warning(f"Error parsing LLM response for compare_contract_object: {error}")
            return False
        return bool(result.get("sont_proches", False))
    except Exception as e:
        logger.error(f"Error calling LLM for compare_contract_object: {e}")
        return False


def compare_batches(llm_val:list[dict[str, str]], ref_val:list[dict[str, str]]):
    """Compare les lots du marché."""
    if llm_val == [] and ref_val == []:
        return True

    if len(llm_val) != len(ref_val):
        return False
    
    for lot_llm in llm_val:
        found = False
        for lot_ref in ref_val:
            if (lot_llm.get('numero_lot') == lot_ref.get('numero_lot') and 
                normalize_string(lot_llm.get('titre_lot')) == normalize_string(lot_ref.get('titre_lot'))):
                found = True
                break
        if not found:
            return False
    return True


def compare_contract_form(llm_val:dict, ref_val:dict):
    """Compare la forme du marché CCAP."""
    if llm_val == {} and ref_val == {}:
        return True
    
    if llm_val.get('structure') != ref_val.get('structure'):
        return False
    
    llm_forme = llm_val.get('forme')
    ref_forme = ref_val.get('forme')
    
    if isinstance(llm_forme, str) and isinstance(ref_forme, str):
        return llm_forme == ref_forme
    
    if isinstance(llm_forme, list) and isinstance(ref_forme, list):
        if len(llm_forme) != len(ref_forme):
            return False
        for forme_llm in llm_forme:
            found = False
            for forme_ref in ref_forme:
                if (forme_llm.get('numero_lot') == forme_ref.get('numero_lot') and
                    compare_contract_form(forme_llm.get('forme', {}), forme_ref.get('forme', {}))):
                    found = True
                    break
            if not found:
                return False
        return True
    
    if isinstance(llm_forme, dict) and isinstance(ref_forme, dict):
        return compare_contract_form(llm_forme, ref_forme)
    
    return False


def compare_batches_duration(llm_val:list[dict], ref_val:list[dict]):
    """Compare la durée des lots."""

    if llm_val == [] and ref_val == []:
        return True
    
    if len(llm_val) != len(ref_val):
        return False
    
    for duree_llm in llm_val:
        found = False
        for duree_ref in ref_val:
            if duree_llm.get('numero_lot') == duree_ref.get('numero_lot'):
                llm_duree = duree_llm.get('duree_lot')
                ref_duree = duree_ref.get('duree_lot')
                if isinstance(llm_duree, str) and isinstance(ref_duree, str):
                    if llm_duree == ref_duree:
                        found = True
                elif isinstance(llm_duree, dict) and isinstance(ref_duree, dict):
                    if (llm_duree.get('duree_initiale') == ref_duree.get('duree_initiale') and
                        llm_duree.get('duree_reconduction') == ref_duree.get('duree_reconduction') and
                        llm_duree.get('nb_reconductions') == ref_duree.get('nb_reconductions') and
                        llm_duree.get('delai_tranche_optionnelle') == ref_duree.get('delai_tranche_optionnelle')):
                        found = True
                break
        if not found:
            return False
    return True


def compare_contract_duration(llm_val:dict, ref_val:dict):
    """Compare la durée du marché."""
    if llm_val == {} and ref_val == {}:
        return True
    if llm_val == {} or ref_val == {}:
        return False
    
    try:
        if llm_val.get('duree_initiale') != ref_val.get('duree_initiale'):
            return False
        if llm_val.get('duree_reconduction') != ref_val.get('duree_reconduction'):
            return False
        if llm_val.get('nb_reconductions') != ref_val.get('nb_reconductions'):
            return False
        if llm_val.get('delai_tranche_optionnelle') != ref_val.get('delai_tranche_optionnelle'):
            return False
        return True
    except (ValueError, TypeError):
        return False


def compare_price_revision_formula(llm_val: str, ref_val: str):
    """Compare la formule de révision des prix."""
    return False


def compare_reference_index(llm_val: str, ref_val: str):
    """Compare l'index de référence."""
    return False


def compare_advance_conditions(llm_val: str, ref_val: str):
    """Compare les conditions d'avance CCAP."""
    return False


def compare_price_revision(llm_val: str, ref_val: str):
    """Compare la révision des prix."""
    return False


def compare_batches_amount(llm_val:list[dict], ref_val:list[dict]):
    """Compare les montants HT des lots."""
    if llm_val == [] and ref_val == []:
        return True
    
    if len(llm_val) != len(ref_val):
        return False
    
    for montant_llm in llm_val:
        found = False
        for montant_ref in ref_val:
            if (montant_llm.get('numero_lot') == montant_ref.get('numero_lot') and
                montant_llm.get('montant_ht_maximum') == montant_ref.get('montant_ht_maximum') and
                montant_llm.get('type_montant') == montant_ref.get('type_montant')):
                found = True
                break
        if not found:
            return False
    return True


def compare_amounts(llm_val: str, ref_val: str):
    """Compare les montants HT."""
    if llm_val == '' and ref_val == '':
        return True
    if llm_val == '' or ref_val == '':
        return False
    return normalize_string(str(llm_val)) == normalize_string(str(ref_val))


def compare_global_contract(llm_val, ref_val):
    """Compare le CCAG."""
    if llm_val == '' and ref_val == '':
        return True
    if llm_val == '' or ref_val == '':
        return False
    return normalize_string(str(llm_val)) == normalize_string(str(ref_val))


def patch_post_processing(df):
    df_patched = df.copy()
    df_patched['llm_response'] = df_patched['llm_response'].apply(
        lambda x: copy.deepcopy(x) if isinstance(x, dict) else x
    )
    post_processing_functions = {


    }

    for idx, row in df_patched.iterrows():
        llm_response = row.get('llm_response', None)
        if llm_response is None or pd.isna(llm_response):
            continue
        
        for key in llm_response.keys():
            if key in post_processing_functions:
                try:
                    llm_response[key] = post_processing_functions[key](llm_response[key])
                    df_patched.at[idx, key] = llm_response[key]
                except Exception as e:
                    logger.warning(f"Error in post_processing_functions for {key}, idx: {idx}: {e}")
                    llm_response[key] = None
                    df_patched.at[idx, key] = None

        df_patched.at[idx, 'llm_response'] = llm_response

    return df_patched


# Mapping des colonnes vers leurs fonctions de comparaison
def get_comparison_functions():
    """
    Retourne le dictionnaire des fonctions de comparaison.
    Cette fonction garantit que les références pointent toujours vers les dernières versions des fonctions,
    même après un rechargement de module.
    
    Returns:
        dict: Dictionnaire associant les noms de colonnes à leurs fonctions de comparaison
    """
    return {
        'objet_marche': compare_contract_object,
        'lots': compare_batches,
        'forme_marche': compare_contract_form,
        'duree_lots': compare_batches_duration,
        'duree_marche': compare_contract_duration,
        'formule_revision_prix': compare_price_revision_formula,
        'index_reference': compare_reference_index,
        'condition_avance': compare_advance_conditions,
        'revision_prix': compare_price_revision,
        'montant_ht_lots': compare_batches_amount,
        'montants_ht': compare_amounts,
        'ccag': compare_global_contract,
    }


def create_batch_test(multi_line_coef = 1):
    """Test de qualité des informations extraites par le LLM."""
    # Chemin vers le fichier CSV de test
    csv_path = CSV_DIR_PATH / "test_ccap.csv"

    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path).iloc[:10]
    df_test.fillna('', inplace=True)
    df_test['lots'] = df_test['lots'].apply(lambda x: json.loads(x))
    df_test['forme_marche'] = df_test['forme_marche'].apply(lambda x: json.loads(x))
    df_test['duree_lots'] = df_test['duree_lots'].apply(lambda x: json.loads(x))
    df_test['duree_marche'] = df_test['duree_marche'].apply(lambda x: json.loads(x))
    df_test['montant_ht_lots'] = df_test['montant_ht_lots'].apply(lambda x: json.loads(x))


    # Post-traitement direct des colonnes du DataFrame de test (après lecture du CSV)
    # Les fonctions post-traitement sont utilisées comme pour patch_post_traitement, mais appliquées colonne par colonne
    POST_PROCESSING_FUNCTIONS = {
        # Ajouter ici d'autres champs si besoin dans le futur
    }

    print(datetime.now())

    for col, post_process_func in POST_PROCESSING_FUNCTIONS.items():
        if col in df_test.columns:
            for idx, val in df_test[col].items():
                try:
                    # On conserve le même format qu'en production: JSON str
                    df_test.at[idx, col] = post_process_func(val)
                except Exception as e:
                    logger.warning(f"Error in post-processing DF_TEST for column {col} at index {idx}: {e}")
                    df_test.at[idx, col] = ''
    
    if multi_line_coef > 1:
        df_test = pd.concat([df_test for x in range(multi_line_coef)]).reset_index(drop=True)

        
    # Création du DataFrame pour l'analyse
    df_analyze = pd.DataFrame()
    df_analyze['filename'] = df_test['filename']
    df_analyze['classification'] = 'ccap'
    df_analyze['relevant_content'] = df_test['text']
    
    # Configuration du LLM
    llm_model = 'albert-large'
    
    # Analyse du contenu avec df_analyze_content
    df_result = df_analyze_content(
        api_key=ALBERT_API_KEY,
        base_url=ALBERT_BASE_URL,
        llm_model=llm_model,
        df=df_analyze.iloc[:10],
        df_attributes=ATTRIBUTES,
        max_workers=20,
        temperature=0.3,
        save_grist=False
    )
    
    df_post_processing = patch_post_processing(df_result)

    # Fusion des résultats avec les valeurs de référence
    # Pour éviter le produit cartésien lorsque filename est dupliqué, on utilise l'index
    # Les deux dataframes ont le même nombre de lignes et le même ordre
    df_post_processing_reset = df_post_processing[['filename', 'llm_response']].reset_index(drop=True)
    df_test_reset = df_test.reset_index(drop=True)
    
    # Ajout d'un identifiant unique basé sur l'index pour le merge
    df_post_processing_reset['_merge_key'] = df_post_processing_reset.index
    df_test_reset['_merge_key'] = df_test_reset.index
    
    # Merge sur l'identifiant unique plutôt que sur filename
    df_merged = df_post_processing_reset.merge(
        df_test_reset,
        on='_merge_key',
        how='inner'
    )
    
    # Suppression de la colonne temporaire et de la colonne filename dupliquée
    df_merged = df_merged.drop(columns=['_merge_key', 'filename_x'])
    df_merged = df_merged.rename(columns={'filename_y': 'filename'})
    
    return df_test, df_result, df_post_processing, df_merged


def check_quality_one_field(df_merged, col_to_test = 'objet_marche'):
    # ============================================================================
    # COMPARAISON POUR UNE COLONNE SPÉCIFIQUE
    # ============================================================================
    
    comparison_func = get_comparison_functions()[col_to_test]
    print(f"\n{'='*80}")
    print(f"Comparaison pour la colonne: {col_to_test}")
    print(f"{'='*80}\n")
    
    # Boucle de comparaison simple
    for idx, row in df_merged.iterrows():
        filename = row.get('filename', 'unknown')
        
        # Récupérer le dict llm_response
        llm_data = row.get('llm_response', None)

        
        # Extraire les valeurs
        ref_val = row.get(col_to_test, None)
        llm_val = llm_data.get(col_to_test, None) if llm_data else None
        
        # Extraction des pbm OCR
        list_pbm_ocr = row.get('pbm_ocr', False)
        pbm_ocr = col_to_test in eval(list_pbm_ocr)

        # Comparer les valeurs
        try:
            match_result = comparison_func(llm_val, ref_val)
            match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
            status = "✅ MATCH" if match_result else "❌ NO MATCH"
            print(f"{status} | {filename} | OCR {"❌" if pbm_ocr else "✅"}")
            print(f"  LLM: {llm_val}")
            print(f"  REF: {ref_val}")
            print()
        except Exception as e:
            print(f"❌ ERREUR | {filename}: {str(e)} | OCR {"❌" if pbm_ocr else "✅"}")
            print(f"  LLM: {llm_val}")
            print(f"  REF: {ref_val}")
            print()


def check_quality_one_row(df_merged, row_idx_to_test = 0, excluded_columns = []):
    # ============================================================================
    # COMPARAISON POUR UNE LIGNE SPÉCIFIQUE
    # ============================================================================
    
    if row_idx_to_test < len(df_merged):
        row = df_merged.iloc[row_idx_to_test]
        filename = row.get('filename', 'unknown')
        
        print(f"\n{'='*80}")
        print(f"Comparaison pour la ligne {row_idx_to_test} (fichier: {filename})")
        print(f"{'='*80}\n")
        
        # Récupérer le dict llm_response
        llm_data = row.get('llm_response', None)
        
        # Comparer toutes les colonnes (sauf exclues)
        for col in get_comparison_functions().keys():
            if col in excluded_columns:
                continue
            if col not in df_merged.columns:
                continue
            
            comparison_func = get_comparison_functions()[col]
            
            # Extraire les valeurs
            ref_val = row.get(col, None)
            llm_val = llm_data.get(col, None) if llm_data else None
            
            # Extraction des pbm OCR
            list_pbm_ocr = row.get('pbm_ocr', False)
            pbm_ocr = col in eval(list_pbm_ocr)

            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                status = "✅ MATCH" if match_result else "❌ NO MATCH"
                print(f"{status} | {col} | OCR {"❌" if pbm_ocr else "✅"}")
                print(f"  LLM: {llm_val}")
                print(f"  REF: {ref_val}")
                print()
            except Exception as e:
                print(f"❌ ERREUR | {col}: {str(e)} | OCR {"❌" if pbm_ocr else "✅"}")
                print(f"  LLM: {llm_val}")
                print(f"  REF: {ref_val}")
                print()
    else:
        print(f"\n❌ Index {row_idx_to_test} invalide. Le DataFrame contient {len(df_merged)} lignes.\n")
    

def check_global_statistics(df_merged, excluded_columns = []):
    # ============================================================================
    # STATISTIQUES GLOBALES DE COMPARAISON
    # ============================================================================
    
    print(f"\n{'='*80}")
    print("STATISTIQUES GLOBALES DE COMPARAISON")
    print(f"{'='*80}\n")
    
    results = {}
    
    # Comparaison pour chaque colonne (sauf exclues)
    for col in get_comparison_functions().keys():
        # Ignorer les colonnes exclues
        if col in excluded_columns:
            continue
        
        # Vérifier si la colonne existe dans le CSV de référence
        if col not in df_merged.columns:
            continue
        
        comparison_func = get_comparison_functions()[col]
        matches = []
        errors = []
        ocr_errors_count = 0
        matches_no_ocr = []
        
        # Comparer toutes les lignes pour cette colonne
        for idx, row in df_merged.iterrows():
            filename = row.get('filename', 'unknown')
            
            # Vérifier les erreurs OCR pour cette colonne
            pbm_ocr = False
            try:
                list_pbm_ocr = row.get('pbm_ocr', False)
                if list_pbm_ocr and list_pbm_ocr != False:
                    pbm_ocr_list = eval(list_pbm_ocr) if isinstance(list_pbm_ocr, str) else list_pbm_ocr
                    if col in pbm_ocr_list:
                        ocr_errors_count += 1
                        pbm_ocr = True
            except Exception:
                # Si erreur lors de l'évaluation, on ignore
                pass
            
            # Récupérer le dict llm_response
            llm_response = row.get('llm_response', None)
            if llm_response is None or pd.isna(llm_response):
                errors.append(f"{filename}: llm_response is None or NaN")
                matches.append(False)
                # Si pas de problème OCR, on compte aussi dans matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(False)
                continue
            
            # Extraire les valeurs
            ref_val = row.get(col, None)
            llm_val = llm_response.get(col, None)
            
            # Comparer les valeurs
            try:
                match_result = comparison_func(llm_val, ref_val)
                match_result = bool(match_result) if not isinstance(match_result, bool) else match_result
                matches.append(match_result)
                # Si pas de problème OCR, on ajoute aussi à matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(match_result)
            except Exception as e:
                errors.append(f"{filename}: Error in comparison_func: {str(e)}")
                matches.append(False)
                # Si pas de problème OCR, on ajoute aussi à matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(False)
        
        # Calculer les statistiques pour cette colonne
        total = len(matches)
        matches_count = sum(matches)
        errors_count = len(errors)
        accuracy = matches_count / total if total > 0 else 0.0
        
        # Calculer l'accuracy sans OCR (seulement sur les comparaisons sans problème OCR)
        total_no_ocr = len(matches_no_ocr)
        matches_no_ocr_count = sum(matches_no_ocr)
        accuracy_no_ocr = matches_no_ocr_count / total_no_ocr if total_no_ocr > 0 else 0.0
        
        results[col] = {
            'total': total,
            'matches': matches_count,
            'errors': errors_count,
            'ocr_errors': ocr_errors_count,
            'accuracy': accuracy,
            'accuracy_no_ocr': accuracy_no_ocr,
            'total_no_ocr': total_no_ocr,
            'matches_no_ocr': matches_no_ocr_count
        }
    
    # Affichage des statistiques
    print(f"{'Colonne':<35} | {'Total':<6} | {'Matches':<8} | {'Erreurs':<8} | {'OCR Errors':<10} | {'Accuracy':<10} | {'Accuracy (no OCR)':<18}")
    print("-" * 120)
    
    for col, result in results.items():
        print(f"{col:<35} | {result['total']:<6} | {result['matches']:<8} | {result['errors']:<8} | {result['ocr_errors']:<10} | {result['accuracy']*100:>6.2f}% | {result['accuracy_no_ocr']*100:>14.2f}%")
    
    print(f"\n{'='*120}")
    print("Résumé global:")
    total_comparisons = sum(r['total'] for r in results.values())
    total_matches = sum(r['matches'] for r in results.values())
    total_errors = sum(r['errors'] for r in results.values())
    total_ocr_errors = sum(r['ocr_errors'] for r in results.values())
    global_accuracy = total_matches / total_comparisons if total_comparisons > 0 else 0.0
    
    # Calculer l'accuracy globale sans OCR
    total_no_ocr = sum(r['total_no_ocr'] for r in results.values())
    total_matches_no_ocr = sum(r['matches_no_ocr'] for r in results.values())
    global_accuracy_no_ocr = total_matches_no_ocr / total_no_ocr if total_no_ocr > 0 else 0.0
    
    print(f"Total de comparaisons: {total_comparisons}")
    print(f"Total de matches: {total_matches}")
    print(f"Total d'erreurs: {total_errors}")
    print(f"Total d'erreurs OCR: {total_ocr_errors}")
    print(f"Accuracy globale: {global_accuracy*100:.2f}%")
    print(f"Accuracy globale (sans OCR): {global_accuracy_no_ocr*100:.2f}% ({total_matches_no_ocr}/{total_no_ocr})")
    print(f"{'='*120}\n")


df_test, df_result, df_post_processing, df_merged = create_batch_test()


EXCLUDED_COLUMNS = [
    'objet_marche',
    'formule_revision_prix',
    'condition_avance',
    'revision_prix'
]

check_quality_one_field(df_merged, col_to_test = 'duree_marche')

check_quality_one_row(df_merged, row_idx_to_test = 1)

check_global_statistics(df_merged, excluded_columns = EXCLUDED_COLUMNS)

# {
#   "objet_marche": "", 
#   "lots": "", 
#   "forme_marche": "", 
#   "duree_lots": "", 
#   "duree_marche": "", 
#   "formule_revision_prix": "", 
#   "index_reference_ccap": "", 
#   "condition_avance_ccap": "", 
#   "revision_prix_ccap": "", 
#   "montant_ht_lots_ccap": "", 
#   "montant_ht_ccap": "", 
#   "ccag_ccap": "" 
# }