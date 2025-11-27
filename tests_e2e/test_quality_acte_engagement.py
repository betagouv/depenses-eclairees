import json
import re
from datetime import datetime
import pandas as pd
import pytest
import logging

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


def compare_object(llm_value, ref_value, llm_model='albert-small'):
    """
    Compare deux objets en utilisant un LLM comme juge pour évaluer la proximité de sens.
    
    Args:
        llm_value: Valeur extraite par le LLM
        ref_value: Valeur de référence
        temperature: Température pour la génération (0.0 = déterministe, 0.2-0.3 = nuance avec cohérence)
                    Par défaut 0.2 pour permettre de la nuance tout en gardant de la reproductibilité.
        
    Returns:
        bool: True si les objets sont sémantiquement proches, False sinon
    """
    # Gestion des valeurs vides ou None
    if (llm_value == '' or llm_value is None or llm_value == 'nan') and (ref_value == '' or ref_value is None or ref_value == 'nan'):
        return True
    
    if (llm_value == '' or llm_value is None or llm_value == 'nan') or (ref_value == '' or ref_value is None or ref_value == 'nan'):
        return False
    
    try:
        # Création d'une instance LLMEnvironment
        llm_env = LLMClient(
            api_key=API_KEY_ALBERT,
            base_url=BASE_URL_PROD,
            llm_model=llm_model
        )
        
        # Construction du prompt pour demander l'avis du LLM
        system_prompt = "Vous êtes un expert en analyse sémantique de documents juridiques. Votre rôle est d'évaluer la proximité de sens entre deux descriptions d'objets."
        
        user_prompt = f"""Compare les deux descriptions d'objet suivantes et détermine si elles décrivent la même chose ou des choses sémantiquement proches.

    Valeur extraite par le LLM: {llm_value}

    Valeur de référence: {ref_value}

    Analyse si ces deux descriptions ont le même sens ou un sens proche. Prends en compte :
    - Les synonymes et formulations équivalentes
    - Les variations de style ou de formulation
    - L'essence et le contenu principal, pas seulement la forme exacte

    Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec cette structure exacte:
    {{
        "sont_proches": true ou false,
        "explication": "brève explication de votre analyse"
    }}"""
        
        message = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}
        
        # Appel au LLM avec format JSON forcé
        # Température 0.2 : permet de la nuance dans l'évaluation sémantique tout en gardant de la cohérence
        response = llm_env.ask_llm(message=message, response_format=response_format, temperature=0.2)
        
        # Parsing de la réponse JSON avec la fonction parse_json_response
        result, error = parse_json_response(response)
        
        if error:
            logger.warning(f"Error parsing LLM response for compare_object: {error}. Response: {response}")
            return False
        
        # print("Réponse LLM : ", result.get("explication", ""))

        return bool(result.get("sont_proches", False))
            
    except Exception as e:
        logger.error(f"Error calling LLM for compare_object: {e}")
        return False


def compare_beneficiary_administration(llm_value, ref_value, llm_model='albert-small'):
    """
    Compare deux administrations bénéficiaires en utilisant un LLM comme juge pour évaluer s'il s'agit du même organisme ou d'une entité publique équivalente.

    Args:
        llm_value: Valeur extraite par le LLM pour l'administration bénéficiaire
        ref_value: Valeur de référence pour l'administration bénéficiaire
    
    Returns:
        bool: True si les administrations bénéficiaires sont identiques ou équivalentes, False sinon
    """
    # Gestion des valeurs vides ou None
    if (llm_value == '' or llm_value is None or llm_value == 'nan') and (ref_value == '' or ref_value is None or ref_value == 'nan'):
        return True

    if (llm_value == '' or llm_value is None or llm_value == 'nan') or (ref_value == '' or ref_value is None or ref_value == 'nan'):
        return False

    try:
        # Création d'une instance LLMEnvironment
        llm_env = LLMClient(
            api_key=API_KEY_ALBERT,
            base_url=BASE_URL_PROD,
            llm_model=llm_model
        )

        # Construction du prompt pour demander l'avis du LLM
        system_prompt = (
            "Vous êtes un expert en analyse de documents administratifs publics. "
            "Votre rôle est d'évaluer si deux chaînes désignent la même administration bénéficiaire (structure administrative ou publique bénéficiaire d'une commande) "
            "ou deux entités publiques équivalentes."
        )

        user_prompt = f"""Compare les deux mentions suivantes concernant l'administration bénéficiaire d'un contrat ou acte administratif, 
        et détermine si elles désignent la même structure, entité ou administration bénéficiaire, ou des administrations strictement équivalentes
        (avec ou sans variation d'intitulé ou de formulation).

        Valeur extraite par le LLM :
        {llm_value}

        Valeur de référence :
        {ref_value}

        Analyse si ces deux valeurs réfèrent à la même administration ou à une entité équivalente. Prends en compte :
        - Les synonymes, reformulations, différences d'intitulé ou d'abréviation (par exemple, 'Préfecture de la région Île-de-France' vs 'Préfecture régionale Île-de-France')
        - Le contexte administratif ou territorial, les rôles correspondant aux structures (par exemple, un intitulé de direction qui désigne l'administration bénéficiaire)
        - Le fait que certaines valeurs peuvent préciser un service ou une direction interne d'une administration (cela compte pour la même administration si l'essentiel concorde)
        - Le format doit être le nom complet, sans acronymes sauf s'ils sont officiels et connus

        Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec cette structure exacte :
        {{
            "sont_equivalentes": true ou false,
            "explication": "brève explication de votre analyse"
        }}"""

        message = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}

        # Appel au LLM avec format JSON forcé, température basse pour fiabilité
        response = llm_env.ask_llm(message=message, response_format=response_format, temperature=0.2)

        # Parsing de la réponse JSON avec la fonction parse_json_response
        result, error = parse_json_response(response)

        if error:
            logger.warning(
                f"Error parsing LLM response for compare_beneficiary_administration: {error}. Response: {response}"
            )
            return False

        print("LLM explanation for administration_beneficiaire: ", result.get("explication", ""))

        return bool(result.get("sont_equivalentes", False))
        
    except Exception as e:
        logger.error(f"Error calling LLM for compare_beneficiary_administration: {e}")
        return False


def compare_main_company(llm_value, ref_value):
    """Compare societe_principale : comparaison de chaînes normalisées."""
    llm_norm = normalize_string(llm_value)
    ref_norm = normalize_string(ref_value)

    if llm_norm == ref_norm:
        return True
    else:
        llm_norm_no_space = llm_norm.replace(" ", "")
        ref_norm_no_space = ref_norm.replace(" ","")
        return llm_norm_no_space == ref_norm_no_space


def compare_siret(llm_value, ref_value):
    """Compare siret : comparaison exacte."""
    if (llm_value == '' or llm_value is None or llm_value == 'nan') and (ref_value == '' or ref_value is None or ref_value == 'nan'):
        return True
    llm_str = str(llm_value) if not pd.isna(llm_value) else ""
    ref_str = str(ref_value) if not pd.isna(ref_value) else ""
    return llm_str == ref_str


def compare_siren(llm_value, ref_value):
    """Compare siren : comparaison exacte."""
    if (llm_value == '' or llm_value is None or llm_value == 'nan') and (ref_value == '' or ref_value is None or ref_value == 'nan'):
        return True
    llm_str = str(llm_value) if not pd.isna(llm_value) else ""
    ref_str = str(ref_value) if not pd.isna(ref_value) else ""
    return llm_str == ref_str


def compare_mandatee_bank_account(llm_val:str, ref_val:str):
    """Compare rib_mandataire : format JSON, comparaison des 5 champs."""

    if (llm_val == '' or llm_val is None or llm_val == 'nan') and (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return True

    elif (llm_val == '' or llm_val is None or llm_val == 'nan'):
        return False
    
    llm_dict = json.loads(llm_val)
    ref_dict = json.loads(ref_val)

    # Si 'iban' est dans ref_dict et non vide, alors on compare les ibans (exact).
    if ref_dict.get('iban', '') != '':
        if llm_dict.get('iban', '') == ref_dict.get('iban', ''):
            return True
        else:
            return False
    else:
        # Si 'iban' absent ou vide dans ref_dict, alors on vérifie qu'il est aussi absent ou vide dans llm_dict, ET que les banques sont les mêmes (normalisées)
        if llm_dict.get('iban', '') != '':
            return False
        # S'il n'y a pas d'iban, on compare les banques (normalisées)
        llm_banque = normalize_string(llm_dict.get('banque', ''))
        ref_banque = normalize_string(ref_dict.get('banque', ''))
        if llm_banque != ref_banque and (not llm_banque in ref_banque and llm_banque != ''):
            return False
        return True


def compare_advance(llm_value, ref_value):
    """Compare avance : renvoie False."""
    return False


def compare_co_contractors(llm_val, ref_val):
    """Compare cotraitants : liste de json, renvoie True si tous les cotraitants LLM sont trouvés côté référence."""
    llm_dict = json.loads(llm_val)
    ref_dict = json.loads(ref_val)

    if len(llm_dict) != len(ref_dict):
        return False
    
    co_contractors_valid = True
    # Pour chaque cotraitant généré par le LLM
    for co_contractor_llm in llm_dict:
        this_co_contractor_valid = False
        # On essaye de le retrouver dans la liste de référence
        for co_contractor_ref in ref_dict:
            # On compare le nom (avec la fonction de normalisation) et le siret
            if compare_main_company(co_contractor_llm['nom'], co_contractor_ref['nom']) and compare_siret(co_contractor_llm['siret'], co_contractor_ref['siret']):
                this_co_contractor_valid = True  # Un match est trouvé
                print("Co-contractor found: ", co_contractor_ref)
                break
        if not this_co_contractor_valid:
            # Si on ne trouve pas ce cotraitant dans les références, on considère la comparaison échouée
            print("Co-contractor not found: ", co_contractor_llm)
            co_contractors_valid = False
            break
    # La fonction ne vérifie pas s'il manque des cotraitants côté LLM
    return co_contractors_valid


def compare_subcontractors(llm_val, ref_val):
    """Compare sous_traitants : liste de json, renvoie True si tous les sous_traitants LLM sont trouvés côté référence."""
    llm_dict = json.loads(llm_val)
    ref_dict = json.loads(ref_val)

    if len(llm_dict) != len(ref_dict):
        return False
    
    subcontractors_valid = True
    # Pour chaque sous_traitant généré par le LLM
    for subcontractor_llm in llm_dict:
        this_subcontractor_valid = False
        # On essaye de le retrouver dans la liste de référence
        for subcontractor_ref in ref_dict:
            # On compare le nom (avec la fonction de normalisation) et le siret
            if compare_main_company(subcontractor_llm['nom'], subcontractor_ref['nom']) and compare_siret(subcontractor_llm['siret'], subcontractor_ref['siret']):
                this_subcontractor_valid = True  # Un match est trouvé
                print("Sous-traitant trouvé : ", subcontractor_ref)
                break
        if not this_subcontractor_valid:
            # Si on ne trouve pas ce sous_traitant dans les références, on considère la comparaison échouée
            print("Sous-traitant non trouvé : ", subcontractor_llm)
            subcontractors_valid = False
            break
    # La fonction ne vérifie pas s'il manque des sous_traitants côté LLM
    return subcontractors_valid


def compare_other_bank_accounts(llm_val:str, ref_val:str):
    """Compare rib_autres : liste de json, renvoie True si tous les comptes bancaires LLM sont trouvés côté référence."""
    if (llm_val == '' or llm_val is None or llm_val == 'nan') and (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return True
    
    if (llm_val == '' or llm_val is None or llm_val == 'nan') or (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return False
    
    llm_list = json.loads(llm_val)
    ref_list = json.loads(ref_val)

    if len(llm_list) != len(ref_list):
        return False
    
    bank_accounts_valid = True
    # Pour chaque compte bancaire généré par le LLM
    for bank_account_llm in llm_list:
        this_bank_account_valid = False
        # On essaye de le retrouver dans la liste de références
        for bank_account_ref in ref_list:
            # On compare le compte bancaire avec la fonction compare_mandatee_bank_account
            if compare_mandatee_bank_account(json.dumps(bank_account_llm), json.dumps(bank_account_ref)):
                this_bank_account_valid = True  # Un match est trouvé
                print("RIB trouvé : ", bank_account_ref)
                break
        if not this_bank_account_valid:
            # Si on ne trouve pas ce compte bancaire dans les références, on considère la comparaison échouée
            print("RIB non trouvé : ", bank_account_llm)
            bank_accounts_valid = False
            break
    # La fonction ne vérifie pas s'il manque des comptes bancaires côté LLM
    return bank_accounts_valid


def compare_amount(llm_val, ref_val):
    """Compare montant : comparaison des valeurs."""
    if (llm_val == '' or llm_val is None or llm_val == 'nan') and (ref_val == '' or ref_val is None or ref_val == 'nan'):
        return True
    # llm_val = post_processing_amount(llm_value)
    # ref_val = post_processing_amount(ref_value)
    return llm_val == ref_val


def parse_date(date_str):
    """Parse une date au format DD/MM/YYYY ou autres formats courants."""
    if pd.isna(date_str) or date_str == "":
        return None
    date_str = str(date_str).strip()
    formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def compare_date(llm_value, ref_value):
    """Compare date : comparaison de dates."""
    llm_date = parse_date(llm_value)
    ref_date = parse_date(ref_value)
    if llm_date is None and ref_date is None:
        return True
    if llm_date is None or ref_date is None:
        return False
    return llm_date == ref_date


def compare_duration(llm_val, ref_val):
    """Compare duree : nombre de mois, comparaison exacte."""
    llm_dict = json.loads(llm_val)
    ref_dict = json.loads(ref_val)
   
    if (llm_dict == '' or llm_dict is None or llm_dict == 'nan') and (ref_dict == '' or ref_dict is None or ref_dict == 'nan'):
        return True

    if (llm_dict == '' or llm_dict is None or llm_dict == 'nan') or (ref_dict == '' or ref_dict is None or ref_dict == 'nan'):
        return False
    
    try:
        if llm_dict.get('duree_initiale', '') != ref_dict.get('duree_initiale', ''):
            return False
        if llm_dict.get('duree_reconduction', '') != ref_dict.get('duree_reconduction', ''):
            return False
        if llm_dict.get('nb_reconductions', '') != ref_dict.get('nb_reconductions', ''):
            return False
        if llm_dict.get('delai_tranche_optionnelle', '') != ref_dict.get('delai_tranche_optionnelle', ''):
            return False
        return True
    except (ValueError, TypeError):
        return False


def patch_post_processing(df):
    df_patched = df.copy()
    post_processing_functions = {
        'rib_mandataire': post_processing_bank_account,
        'montant_ttc': post_processing_amount,
        'montant_ht': post_processing_amount,
        'cotraitants': post_processing_co_contractors,
        'sous_traitants': post_processing_subcontractors,
        'siret_mandataire': post_processing_siret,
        'duree': post_processing_duration,
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
        'objet_marche': compare_object,
        'administration_beneficiaire': compare_beneficiary_administration,
        'societe_principale': compare_main_company,
        'siret_mandataire': compare_siret,
        'siren_mandataire': compare_siren,
        'rib_mandataire': compare_mandatee_bank_account,
        'avance': compare_advance,
        'cotraitants': compare_co_contractors,
        'sous_traitants': compare_subcontractors,
        'rib_autres': compare_other_bank_accounts,
        'montant_ttc': compare_amount,
        'montant_ht': compare_amount,
        'date_signature_mandataire': compare_date,
        'date_signature_administration': compare_date,
        'date_notification': compare_date,
        'duree': compare_duration,
    }


def create_batch_test(multi_line_coef = 1):
    """Test de qualité des informations extraites par le LLM."""
    # Chemin vers le fichier CSV de test
    csv_path = "/Users/dinum-284659/dev/data/test/test_acte_engagement.csv"
    
    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path).astype(str)
    df_test['siret_mandataire'] = df_test['siret_mandataire'].apply(lambda x: x.split('.')[0])
    df_test['siren_mandataire'] = df_test['siren_mandataire'].apply(lambda x: x.split('.')[0])
    df_test.fillna('', inplace=True)

    # Post-traitement direct des colonnes du DataFrame de test (après lecture du CSV)
    # Les fonctions post-traitement sont utilisées comme pour patch_post_traitement, mais appliquées colonne par colonne
    POST_PROCESSING_FUNCTIONS = {
        'rib_mandataire': post_processing_bank_account,
        'cotraitants': post_processing_co_contractors,
        'sous_traitants': post_processing_subcontractors,
        'duree': post_processing_duration,
        'montant_ttc': post_processing_amount,
        'montant_ht': post_processing_amount,
        'siret_mandataire': post_processing_siret
        # Ajouter ici d'autres champs si besoin dans le futur
    }
    
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
    df_analyze['classification'] = 'acte_engagement'
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


def check_quality_one_field(df_merged, col_to_test = 'duree'):
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

EXCLUDED_COLUMNS = [
    'objet_marche', 
    'administration_beneficiaire', 
    'avance', 
    'cotraitants', 
    'sous_traitants', 
    'rib_autres'
]

check_quality_one_field(df_merged, col_to_test = 'duree')

check_quality_one_row(df_merged, row_idx_to_test = 0, excluded_columns = EXCLUDED_COLUMNS)

check_quality_one_field(df_merged, col_to_test = 'cotraitants')

check_global_statistics(df_merged, excluded_columns = ['avance', 'rib_autres','administration_beneficiaire','objet_marche'])
