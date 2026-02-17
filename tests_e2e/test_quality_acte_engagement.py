import json
import logging
import os
import sys
from datetime import datetime

import django

import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()


from app.grist.grist_api import get_data_from_grist  # noqa: E402
from docia.file_processing.processor.analyze_content import LLMClient  # noqa: E402
from tests_e2e.test_quality_rib import compare_iban  # noqa: E402
from tests_e2e.utils import (  # noqa: E402
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_one_field,
    check_quality_one_row,
    get_fields_with_comparison_errors,
    normalize_string,
    compare_exact_string,
)

logger = logging.getLogger("docia." + __name__)


def compare_object(llm_value, ref_value, llm_model="openweight-medium"):
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
        llm_env = LLMClient()

        # Construction du prompt pour demander l'avis du LLM
        system_prompt = (
            "Vous êtes un expert en analyse sémantique de documents juridiques. "
            "Votre rôle est d'évaluer la proximité de sens entre deux descriptions d'objets."
        )

        user_prompt = f"""
            Compare les deux descriptions d'objet suivantes et détermine si elles décrivent 
            la même chose ou des choses sémantiquement proches.

            Valeur extraite par le LLM: {llm_value}

            Valeur de référence: {ref_value}

            Analyse si ces deux descriptions ont le même sens ou un sens proche. Prends en compte :
            - Les synonymes et formulations équivalentes
            - Les variations de style ou de formulation
            - L'essence et le contenu principal, pas seulement la forme exacte

            Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec 
            cette structure exacte:
            {{
                "sont_proches": true ou false,
                "explication": "brève explication de votre analyse"
            }}
        """
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}

        # Appel au LLM avec format JSON forcé
        # Température 0.2 : permet de la nuance dans l'évaluation sémantique tout en gardant de la cohérence
        result = llm_env.ask_llm(messages=messages, model=llm_model, response_format=response_format, temperature=0)

        # print("Réponse LLM : ", result.get("explication", ""))

        return bool(result.get("sont_proches", False))

    except Exception as e:
        logger.error(f"Error calling LLM for compare_object: {e}")
        return False


def compare_beneficiary_administration(llm_value, ref_value, llm_model="albert-small"):
    """
    Compare deux administrations bénéficiaires en utilisant un LLM comme juge pour évaluer s'il s'agit du même
    organisme ou d'une entité publique équivalente.

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
        llm_env = LLMClient()

        # Construction du prompt pour demander l'avis du LLM
        system_prompt = (
            "Vous êtes un expert en analyse de documents administratifs publics. "
            "Votre rôle est d'évaluer si deux chaînes désignent la même administration bénéficiaire (structure "
            "administrative ou publique bénéficiaire d'une commande) "
            "ou deux entités publiques équivalentes."
        )

        user_prompt = f"""
            Compare les deux mentions suivantes concernant l'administration bénéficiaire d'un 
            contrat ou acte administratif, et détermine si elles désignent la même structure, 
            entité ou administration bénéficiaire, ou des administrations équivalentes (avec 
            ou sans variation d'intitulé ou de formulation). Par exemple, si la valeur extraite 
            par le LLM est plus précise que la valeur de référence, alors on considère que les 
            deux administrations sont équivalentes.

            Valeur extraite par le LLM :
            {llm_value}

            Valeur de référence :
            {ref_value}

            Analyse si ces deux valeurs réfèrent à la même administration ou à une entité équivalente. 
            Prends en compte :
            - Les synonymes, reformulations, différences d'intitulé ou d'abréviation (par exemple, 
              'Préfecture de la région Île-de-France' vs 'Préfecture régionale Île-de-France')
            - Le contexte administratif ou territorial, les rôles correspondant aux structures (par exemple, 
              un intitulé de direction qui désigne l'administration bénéficiaire)
            - Le fait que certaines valeurs peuvent préciser un service ou une direction interne d'une administration 
              (cela compte pour la même administration si l'essentiel concorde)
            - Le format doit être le nom complet, sans acronymes sauf s'ils sont officiels et connus
            
            Tu dois IMPÉRATIVEMENT répondre UNIQUEMENT avec un JSON valide, sans aucun autre texte, avec cette 
            structure exacte :
            {{
                "sont_equivalentes": true ou false,
                "explication": "brève explication de votre analyse"
            }}
        """

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        # Format de réponse JSON forcé
        response_format = {"type": "json_object"}

        # Appel au LLM avec format JSON forcé, température basse pour fiabilité
        result = llm_env.ask_llm(messages=messages, model=llm_model, response_format=response_format, temperature=0)

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
        ref_norm_no_space = ref_norm.replace(" ", "")
        return llm_norm_no_space == ref_norm_no_space


def compare_mandatee_bank_account(llm_val: dict[str, str], ref_val: dict[str, str]):
    """Compare rib_mandataire : format JSON, comparaison des champs IBAN et banque.

    - Si les deux IBANs sont non vides/non None, on valide si compare_iban renvoie True (les banques ne comptent pas alors).
    - Si les deux IBANs sont vides ou None, on valide si les banques sont équivalentes.
    - Si un seul IBAN est non vide, alors False.
    """

    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    llm_iban = llm_val.get("iban")
    ref_iban = ref_val.get("iban")

    llm_banque = normalize_string(llm_val.get("banque", ""))
    ref_banque = normalize_string(ref_val.get("banque", ""))

    # Si les IBAN sont présents dans les deux, compare uniquement les IBAN
    if llm_iban and ref_iban:
        return compare_iban(llm_iban, ref_iban)

    # Si les IBAN sont tous les deux vides, compare la banque
    elif not llm_iban and not ref_iban:
        return llm_banque == ref_banque

    # Si un seul IBAN est vide, on considère que c'est différent
    return False


def compare_co_contractors(llm_val: list[dict[str, str]], ref_val: list[dict[str, str]]):
    """Compare cotraitants : liste de json, renvoie True si tous les cotraitants LLM sont trouvés côté référence."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    def _item_is_in_list(item, search_list, excluded):
        for i, search_item in enumerate(search_list):
            if i in excluded:
                continue
            if compare_main_company(search_item["nom"], item["nom"]) and compare_exact_string(
                search_item["siret"], item["siret"]
            ):
                return i
        return None

    missing_co_contractors = []  # Le co traitants qui n'ont pas été trouvés par le llm
    additional_co_contractors = []  # Les co traitants trouvés par le llm mais qui n'existent pas
    found_ref = []
    found_llm = []
    for i, ref_item in enumerate(ref_val):
        found_item = _item_is_in_list(ref_item, llm_val, excluded=found_llm)
        if found_item is not None:
            found_ref.append(i)
            found_llm.append(found_item)
        else:
            missing_co_contractors.append(ref_item)
    for i, llm_item in enumerate(llm_val):
        if i not in found_llm:
            additional_co_contractors.append(llm_item)

    for x in missing_co_contractors:
        print("Co-contractor not found:", x)
    for x in additional_co_contractors:
        print("Co-contractor allucination:", x)

    return not missing_co_contractors and not additional_co_contractors


def compare_subcontractors(llm_val: list[dict[str, str]], ref_val: list[dict[str, str]]):
    """
    Compare sous_traitants : liste de json, renvoie True si tous les sous_traitants LLM sont trouvés côté référence.
    """

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
            if compare_main_company(subcontractor_llm["nom"], subcontractor_ref["nom"]) and compare_siret(
                subcontractor_llm["siret"], subcontractor_ref["siret"]
            ):
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


def compare_other_bank_accounts(llm_val: list[dict[str, dict[str, str]]], ref_val: list[dict[str, dict[str, str]]]):
    """Compare rib_autres : liste de json, renvoie True si tous les comptes bancaires LLM sont trouvés
    côté référence."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    def _item_is_in_list(item, search_list, excluded):
        for i, search_item in enumerate(search_list):
            if i in excluded:
                continue
            if compare_mandatee_bank_account(item, search_item):
                return i
        return None

    missing_items = []  # Le items qui n'ont pas été trouvés par le llm
    additional_items = []  # Les items trouvés par le llm mais qui n'existent pas
    found_ref = []
    found_llm = []
    for i, ref_item in enumerate(ref_val):
        found_item = _item_is_in_list(ref_item, llm_val, excluded=found_llm)
        if found_item is not None:
            found_ref.append(i)
            found_llm.append(found_item)
        else:
            missing_items.append(ref_item)
    for i, llm_item in enumerate(llm_val):
        if i not in found_llm:
            additional_items.append(llm_item)

    for x in missing_items:
        print("Bank account not found:", x)
    for x in additional_items:
        print("Bank account allucination:", x)

    return not missing_items and not additional_items


def parse_date(date_str):
    """Parse une date au format DD/MM/YYYY ou autres formats courants."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]
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
        if llm_val.get("duree_initiale") != ref_val.get("duree_initiale"):
            return False
        if llm_val.get("duree_reconduction") != ref_val.get("duree_reconduction"):
            return False
        if llm_val.get("nb_reconductions") != ref_val.get("nb_reconductions"):
            return False
        if llm_val.get("delai_tranche_optionnelle") != ref_val.get("delai_tranche_optionnelle"):
            return False
        return True
    except (ValueError, TypeError):
        return False


def compare_montants_en_annexe(llm_val, ref_val):
    """Compare montants_en_annexe : dict avec annexe_financière (bool|null) et classification (null | list[str])."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if llm_val.get("annexe_financière") != ref_val.get("annexe_financière"):
        return False

    llm_cl, ref_cl = llm_val.get("classification"), ref_val.get("classification")
    
    if llm_cl is None and ref_cl is None:
        return True
    if llm_cl is None or ref_cl is None:
        return False

    return sorted(llm_cl) == sorted(ref_cl)


def compare_contract_form(llm_val, ref_val):
    """
    Compare forme_marche : comparaison exacte de chaque sous-champ.
    Structure attendue : lot_concerne (dict avec numero_lot, titre_lot), marche_subsequent (bool),
    marche_parent (str).
    """
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if llm_val.get("lot_concerne") != ref_val.get("lot_concerne"):
        return False
    if llm_val.get("marche_subsequent") != ref_val.get("marche_subsequent"):
        return False
    if llm_val.get("marche_parent") != ref_val.get("marche_parent"):
        return False
    return True


def get_comparison_functions():
    """Mapping des colonnes vers leurs fonctions de comparaison

    Retourne le dictionnaire des fonctions de comparaison.
    Cette fonction garantit que les références pointent toujours vers les dernières versions des fonctions,
    même après un rechargement de module.

    Returns:
        dict: Dictionnaire associant les noms de colonnes à leurs fonctions de comparaison
    """
    return {
        "objet_marche": compare_object,
        "administration_beneficiaire": compare_beneficiary_administration,
        "societe_principale": compare_main_company,
        "siret_mandataire": compare_exact_string,
        "siren_mandataire": compare_exact_string,
        "rib_mandataire": compare_mandatee_bank_account,
        "cotraitants": compare_co_contractors,
        "sous_traitants": compare_subcontractors,
        "rib_autres": compare_other_bank_accounts,
        "montant_ttc": compare_exact_string,
        "montant_ht": compare_exact_string,
        "date_signature_mandataire": compare_date,
        "date_signature_administration": compare_date,
        "date_notification": compare_date,
        "duree": compare_duration,
        "conserve_avance": compare_exact_string,
        "montants_en_annexe": compare_montants_en_annexe,
        "forme_marche": compare_contract_form,
        "code_cpv": compare_exact_string,
        "montant_tva": compare_exact_string,
        "mode_consultation": compare_exact_string,
        "mode_reconduction": compare_exact_string,
        "ligne_imputation_budgetaire": compare_exact_string,
    }


def create_batch_test(multi_line_coef=1, max_workers=10, llm_model="openweight-medium", debug_mode=False):
    """Test de qualité des informations extraites par le LLM."""

    # Lecture du fichier CSV
    df_test = get_data_from_grist(table="Acte_engagement_gt_v2")
    df_test["montant_ht"] = df_test["montant_ht"].apply(lambda x: f"{float(x):.2f}" if x else "")
    df_test["montant_ttc"] = df_test["montant_ttc"].apply(lambda x: f"{float(x):.2f}" if x else "")
    df_test["montant_tva"] = df_test["montant_tva"].apply(lambda x: f"{float(x):.2f}" if x else "")
    df_test["rib_mandataire"] = df_test["rib_mandataire"].apply(lambda x: json.loads(x))
    df_test["cotraitants"] = df_test["cotraitants"].apply(lambda x: json.loads(x))
    df_test["sous_traitants"] = df_test["sous_traitants"].apply(lambda x: json.loads(x))
    df_test["duree"] = df_test["duree"].apply(lambda x: json.loads(x))
    df_test["rib_autres"] = df_test["rib_autres"].apply(lambda x: json.loads(x))
    df_test["montants_en_annexe"] = df_test["montants_en_annexe"].apply(lambda x: json.loads(x))
    df_test["forme_marche"] = df_test["forme_marche"].apply(lambda x: json.loads(x))
    
    # Lancement du test
    return analyze_content_quality_test(df_test, "acte_engagement", multi_line_coef=multi_line_coef, max_workers=max_workers, llm_model=llm_model, debug_mode=debug_mode)

if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test(llm_model="openweight-medium", debug_mode=True, max_workers=30)

    EXCLUDED_COLUMNS = ["objet_marche", "administration_beneficiaire"]

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, 'mode_reconduction', comparison_functions, only_errors=True)

    check_quality_one_row(df_merged, 26, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

    fields_with_errors = get_fields_with_comparison_errors(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
    
    for v in fields_with_errors.values():
        print(json.dumps(v))



    
