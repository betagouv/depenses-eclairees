import json
from datetime import datetime
import logging
import os
import sys

import django
from django.conf import settings

import pandas as pd

sys.path.append(".")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'docia.settings')
django.setup()

from app.processor.analyze_content import LLMClient

from tests_e2e.utils import normalize_string, analyze_content_quality_test, check_quality_one_field, \
    check_quality_one_row, check_global_statistics

logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()


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
    if not llm_value and not ref_value:
        return True
    
    if not llm_value or not ref_value:
        return False
    
    try:
        # Création d'une instance LLMEnvironment
        llm_env = LLMClient(llm_model=llm_model)
        
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
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}
        
        # Appel au LLM avec format JSON forcé
        # Température 0.2 : permet de la nuance dans l'évaluation sémantique tout en gardant de la cohérence
        result = llm_env.ask_llm(messages=messages, response_format=response_format, temperature=0)

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
    if not llm_value and not ref_value:
        return True

    if not llm_value or not ref_value:
        return False

    try:
        # Création d'une instance LLMEnvironment
        llm_env = LLMClient(llm_model=llm_model)

        # Construction du prompt pour demander l'avis du LLM
        system_prompt = (
            "Vous êtes un expert en analyse de documents administratifs publics. "
            "Votre rôle est d'évaluer si deux chaînes désignent la même administration bénéficiaire (structure administrative ou publique bénéficiaire d'une commande) "
            "ou deux entités publiques équivalentes."
        )

        user_prompt = f"""Compare les deux mentions suivantes concernant l'administration bénéficiaire d'un contrat ou acte administratif, 
        et détermine si elles désignent la même structure, entité ou administration bénéficiaire, ou des administrations équivalentes
        (avec ou sans variation d'intitulé ou de formulation). Par exemple, si la valeur extraite par le LLM est plus précise que la valeur de référence, 
        alors on considère que les deux administrations sont équivalentes.

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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}

        # Appel au LLM avec format JSON forcé, température basse pour fiabilité
        result = llm_env.ask_llm(messages=messages, response_format=response_format, temperature=0)

        # print("LLM explanation for administration_beneficiaire: ", result.get("explication", ""))

        return bool(result.get("sont_equivalentes", False))
        
    except Exception as e:
        logger.error(f"Error calling LLM for compare_beneficiary_administration: {e}")
        return False


def compare_main_company(llm_value, ref_value):
    """Compare societe_principale : comparaison de chaînes normalisées."""

    if not llm_value and not ref_value:
        return True

    if not llm_value or not ref_value:
        return False

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

    # Gestion des valeurs vides ou None
    if not llm_value and not ref_value:
        return True

    if not llm_value or not ref_value:
        return False


    llm_str = str(llm_value) if not pd.isna(llm_value) else ""
    ref_str = str(ref_value) if not pd.isna(ref_value) else ""
    return llm_str == ref_str


def compare_siren(llm_value, ref_value):
    """Compare siren : comparaison exacte."""
    # Gestion des valeurs vides ou None
    if not llm_value and not ref_value:
        return True

    if not llm_value or not ref_value:
        return False

    llm_str = str(llm_value) if not pd.isna(llm_value) else ""
    ref_str = str(ref_value) if not pd.isna(ref_value) else ""
    return llm_str == ref_str


def compare_mandatee_bank_account(llm_val:dict[str, str], ref_val:dict[str, str]):
    """Compare rib_mandataire : format JSON, comparaison des 5 champs."""

    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False
    
    # Si 'iban' est dans ref_dict et non vide, alors on compare les ibans (exact).
    if ref_val.get('iban', '') != '':
        if llm_val.get('iban', '') == ref_val.get('iban', ''):
            return True
        else:
            return False
    else:
        # Si 'iban' absent ou vide dans ref_dict, alors on vérifie qu'il est aussi absent ou vide dans llm_dict, ET que les banques sont les mêmes (normalisées)
        if llm_val.get('iban', '') != '':
            return False
        # S'il n'y a pas d'iban, on compare les banques (normalisées)
        llm_banque = normalize_string(llm_val.get('banque', ''))
        ref_banque = normalize_string(ref_val.get('banque', ''))
        if llm_banque != ref_banque and (not llm_banque in ref_banque and llm_banque != ''):
            return False
        return True


def compare_advance(llm_value, ref_value):
    """Compare avance : renvoie False."""
    return False


def compare_co_contractors(llm_val:list[dict[str, str]], ref_val:list[dict[str, str]]):
    """Compare cotraitants : liste de json, renvoie True si tous les cotraitants LLM sont trouvés côté référence."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False
    
    co_contractors_valid = True
    # Pour chaque cotraitant généré par le LLM
    for co_contractor_llm in llm_val:
        this_co_contractor_valid = False
        # On essaye de le retrouver dans la liste de référence
        for co_contractor_ref in ref_val:
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


def compare_subcontractors(llm_val:list[dict[str, str]], ref_val:list[dict[str, str]]):
    """Compare sous_traitants : liste de json, renvoie True si tous les sous_traitants LLM sont trouvés côté référence."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False
    
    subcontractors_valid = True
    # Pour chaque sous_traitant généré par le LLM
    for subcontractor_llm in llm_val:
        this_subcontractor_valid = False
        # On essaye de le retrouver dans la liste de référence
        for subcontractor_ref in ref_val:
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


def compare_other_bank_accounts(llm_val:list[dict[str, dict[str, str]]], ref_val:list[dict[str, dict[str, str]]]):
    """Compare rib_autres : liste de json, renvoie True si tous les comptes bancaires LLM sont trouvés côté référence."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False
    
    bank_accounts_valid = True
    # Pour chaque compte bancaire généré par le LLM
    for bank_account_llm in llm_val:
        this_bank_account_valid = False
        # On essaye de le retrouver dans la liste de références
        for bank_account_ref in ref_val:
            # On compare le compte bancaire avec la fonction compare_mandatee_bank_account
            if compare_mandatee_bank_account(bank_account_llm, bank_account_ref):
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
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False
        
    return llm_val == ref_val


def parse_date(date_str):
    """Parse une date au format DD/MM/YYYY ou autres formats courants."""
    if not date_str:
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

    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
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


def get_comparison_functions():
    """ Mapping des colonnes vers leurs fonctions de comparaison

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
    csv_path = CSV_DIR_PATH / "test_acte_engagement.csv"
    
    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path)
    df_test.fillna('', inplace=True)
    df_test['rib_mandataire'] = df_test['rib_mandataire'].apply(lambda x: json.loads(x))
    df_test['cotraitants'] = df_test['cotraitants'].apply(lambda x: json.loads(x))
    df_test['sous_traitants'] = df_test['sous_traitants'].apply(lambda x: json.loads(x))
    df_test['duree'] = df_test['duree'].apply(lambda x: json.loads(x))
    df_test['rib_autres'] = df_test['rib_autres'].apply(lambda x: json.loads(x))
    df_test['siret_mandataire'] = df_test['siret_mandataire'].astype(str).apply(lambda x: x.split('.')[0])
    df_test['siren_mandataire'] = df_test['siren_mandataire'].astype(str).apply(lambda x: x.split('.')[0])

    # Lancement du test
    return analyze_content_quality_test(df_test, "acte_engagement", multi_line_coef=multi_line_coef)


df_test, df_result, df_merged = create_batch_test()

EXCLUDED_COLUMNS = [
    'objet_marche', 
    'administration_beneficiaire', 
    'avance'
]


comparison_functions = get_comparison_functions()

check_quality_one_field(df_merged, 'rib_mandataire', comparison_functions['rib_mandataire'])

check_quality_one_row(df_merged, 0, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

check_quality_one_field(df_merged, 'cotraitants', comparison_functions['cotraitants'])

check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
