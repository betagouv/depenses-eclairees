import json
import re
from datetime import datetime
import pandas as pd
import pytest
import logging
from datetime import datetime

import sys
sys.path.append(".")

from app.processor.analyze_content import df_analyze_content, LLMClient, parse_json_response
from app.processor.attributes_query import ATTRIBUTES
from app.ai_models.config_albert import API_KEY_ALBERT, BASE_URL_PROD
from app.processor.post_processing_llm import *

logger = logging.getLogger("docia." + __name__)

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


def compare_iban(llm_val:str, ref_val:str):
    """Compare l'IBAN : comparaison des valeurs."""
    if (llm_val == '' or llm_val is None or llm_val == 'nan') and (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return True
    return llm_val == ref_val


def compare_bic(llm_val:str, ref_val:str):
    """Compare le BIC : comparaison des valeurs."""
    if (llm_val == '' or llm_val is None or llm_val == 'nan') and (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return True
    return llm_val == ref_val


def compare_bank(llm_val:str, ref_val:str):
    """Compare la banque : comparaison des valeurs."""
    llm_norm = normalize_string(llm_val)
    ref_norm = normalize_string(ref_val)

    if llm_norm == ref_norm:
        return True
    else:
        llm_norm_no_space = llm_norm.replace(" ", "")
        ref_norm_no_space = ref_norm.replace(" ","")
        return llm_norm_no_space == ref_norm_no_space


def compare_account_owner(llm_val:str, ref_val:str):
    """Compare le titulaire du compte : comparaison des valeurs."""
    llm_norm = normalize_string(llm_val)
    ref_norm = normalize_string(ref_val)

    if llm_norm == ref_norm:
        return True
    else:
        llm_norm_no_space = llm_norm.replace(" ", "")
        ref_norm_no_space = ref_norm.replace(" ","")
        return llm_norm_no_space == ref_norm_no_space


def compare_address(llm_val:str, ref_val:str):
    """Compare l'adresse : comparaison des valeurs selon la structure JSON.
    
    Structure attendue : {
        'numero_voie': 'le numéro de voie',
        'nom_voie': 'le nom de la voie',
        'complement_adresse': 'le complément d'adresse éventuel',
        'code_postal': 'le code postal',
        'ville': 'la ville',
        'pays': 'le pays'
    }
    """
    # Gestion des valeurs vides/None/nan
    if (llm_val == '' or llm_val is None or llm_val == 'nan') and (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return True
    if (llm_val == '' or llm_val is None or llm_val == 'nan') or (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return False
    
    llm_dict = json.loads(llm_val)
    ref_dict = json.loads(ref_val)
    
    # Liste des champs à comparer
    fields = ['numero_voie', 'nom_voie', 'complement_adresse', 'code_postal', 'ville', 'pays']
    
    # Comparer chaque champ
    for field in fields:
        llm_field_val = llm_dict.get(field, '')
        ref_field_val = ref_dict.get(field, '')
        
        # Normaliser les valeurs vides
        llm_field_val = llm_field_val.strip().title()
        ref_field_val = llm_field_val.strip().title()
        
        # Comparer les valeurs du champ
        if llm_field_val != ref_field_val:
            return False
    
    return True


def compare_domiciliation(llm_val:str, ref_val:str):
    """Compare la domiciliation : comparaison des valeurs."""
    if (llm_val == '' or llm_val is None or llm_val == 'nan') and (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return True
    return llm_val == ref_val


def patch_post_processing(df):
    df_patched = df.copy()
    post_processing_functions = {
        'iban': post_processing_iban,
        'bic': post_processing_bic,
        'adresse_postale_titulaire': post_processing_postal_address
    }

    for idx, row in df_patched.iterrows():
        llm_response = row.get('llm_response', None)
        if llm_response is None or pd.isna(llm_response):
            continue
        llm_data = json.loads(llm_response) if isinstance(llm_response, str) else llm_response
        
        for key in llm_data.keys():
            if key in post_processing_functions:
                try:
                    llm_data[key] = post_processing_functions[key](llm_data[key])
                    df_patched.loc[idx, key] = json.dumps(llm_data[key])
                except Exception as e:
                    logger.warning(f"Error in post_processing_functions for {key}, idx: {idx}: {e}")
                    llm_data[key] = ''
                    df_patched.loc[idx, key] = ''

        df_patched.loc[idx, 'llm_response'] = json.dumps(llm_data)

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
        'iban': compare_iban,
        'bic': compare_bic,
        'titulaire_compte': compare_account_owner,
        'adresse_postale_titulaire': compare_address,
        'domiciliation': compare_domiciliation,
        'banque': compare_bank,
    }


def create_batch_test(multi_line_coef = 1):
    """Test de qualité des informations extraites par le LLM."""
    # Chemin vers le fichier CSV de test
    csv_path = "/Users/dinum-284659/dev/data/test/test_rib.csv"
    
    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path).astype(str)
    df_test.fillna('', inplace=True)

    # Post-traitement direct des colonnes du DataFrame de test (après lecture du CSV)
    # Les fonctions post-traitement sont utilisées comme pour patch_post_traitement, mais appliquées colonne par colonne
    POST_PROCESSING_FUNCTIONS = {
        'iban': post_processing_iban,
        'bic': post_processing_bic,
        'adresse_postale_titulaire': post_processing_postal_address
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
    df_analyze['classification'] = 'rib'
    df_analyze['relevant_content'] = df_test['text']
    
    # Configuration du LLM
    llm_model = 'albert-large'
    
    # Analyse du contenu avec df_analyze_content
    df_result = df_analyze_content(
        api_key=API_KEY_ALBERT,
        base_url=BASE_URL_PROD,
        llm_model=llm_model,
        df=df_analyze,
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
    
    return df_merged


def check_quality_one_field(df_merged, col_to_test = 'iban'):
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
        
        # Parser le JSON de llm_response
        llm_data = json.loads(row.get('llm_response', None))

        
        # Extraire les valeurs
        ref_val = row.get(col_to_test, None)
        llm_val = llm_data.get(col_to_test, None)

        if isinstance(llm_val, dict):
            llm_val = json.dumps(llm_val)
        
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
        
        # Parser le JSON de llm_response
        llm_data = json.loads(row.get('llm_response', None))
        
        # Comparer toutes les colonnes (sauf exclues)
        for col in get_comparison_functions().keys():
            if col in excluded_columns:
                continue
            if col not in df_merged.columns:
                continue
            
            comparison_func = get_comparison_functions()[col]
            
            # Extraire les valeurs
            ref_val = row.get(col, None)
            llm_val = llm_data.get(col, None)
            
            if isinstance(llm_val, dict):
                llm_val = json.dumps(llm_val)
            
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
            
            # Parser le JSON de llm_response
            try:
                llm_response = row.get('llm_response', None)
                if llm_response is None or pd.isna(llm_response):
                    errors.append(f"{filename}: llm_response is None or NaN")
                    matches.append(False)
                    # Si pas de problème OCR, on compte aussi dans matches_no_ocr
                    if not pbm_ocr:
                        matches_no_ocr.append(False)
                    continue
                
                llm_data = json.loads(llm_response) if isinstance(llm_response, str) else llm_response
            except (json.JSONDecodeError, TypeError) as e:
                errors.append(f"{filename}: JSON parsing error: {str(e)}")
                matches.append(False)
                # Si pas de problème OCR, on compte aussi dans matches_no_ocr
                if not pbm_ocr:
                    matches_no_ocr.append(False)
                continue
            
            # Extraire les valeurs
            ref_val = row.get(col, None)
            llm_val = llm_data.get(col, None)
            
            # Convertir les dict en JSON string (cohérent avec la partie de débogage)
            if isinstance(llm_val, dict):
                llm_val = json.dumps(llm_val)
            
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


df_merged = create_batch_test()

check_quality_one_field(df_merged, col_to_test = 'iban')

check_quality_one_row(df_merged, row_idx_to_test = 26)

check_global_statistics(df_merged, excluded_columns = ['domiciliation', 'banque'])