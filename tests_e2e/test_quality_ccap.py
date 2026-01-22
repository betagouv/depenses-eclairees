import json
import logging
import os
import sys

import django
from django.conf import settings

import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from docia.file_processing.processor.analyze_content import LLMClient  # noqa: E402
from tests_e2e.utils import (  # noqa: E402
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_one_field,
    check_quality_one_row,
    normalize_string,
)

logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()


def compare_contract_object(llm_val, ref_val, llm_model="albert-small"):
    """Compare l'objet du marché CCAP."""
    if not llm_val and not ref_val:
        return True
    if not llm_val or not ref_val:
        return False

    try:
        llm_env = LLMClient(llm_model=llm_model)
        system_prompt = (
            "Vous êtes un expert en analyse sémantique de documents juridiques. "
            "Votre rôle est d'évaluer la proximité de sens entre deux descriptions d'objets."
        )
        user_prompt = f"""
            Compare les deux descriptions d'objet de marché suivantes et détermine si 
            elles décrivent la même chose.

            Valeur extraite par le LLM: {llm_val}
            Valeur de référence: {ref_val}

            Réponds UNIQUEMENT avec un JSON valide:
            {{
                "sont_proches": true ou false,
                "explication": "brève explication"
            }}
        """
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        result = llm_env.ask_llm(messages=messages, response_format={"type": "json_object"}, temperature=0)
        return bool(result.get("sont_proches", False))
    except Exception as e:
        logger.error(f"Error calling LLM for compare_contract_object: {e}")
        return False


def compare_lots_title(llm_val: list[dict[str, str]], ref_val: list[dict[str, str]]):
    """Compare les lots du marché."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    for ref, llm in zip(ref_val, llm_val):
        if normalize_string(ref) != normalize_string(llm):
            return False
    return True


def compare_contract_form(llm_val: dict, ref_val: dict):
    """Compare la forme du marché CCAP."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    llm_structure = llm_val.get("structure")
    ref_structure = ref_val.get("structure")
    llm_tranches = llm_val.get("tranches")
    ref_tranches = ref_val.get("tranches")
    llm_forme_prix = llm_val.get("forme_prix")
    ref_forme_prix = ref_val.get("forme_prix")

    return llm_structure == ref_structure and llm_tranches == ref_tranches and llm_forme_prix == ref_forme_prix


def compare_lots_contract_form(llm_val: list[dict], ref_val: list[dict]):
    """Compare la forme des lots du marché."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    for ref, llm in zip(ref_val, llm_val):
        if not compare_contract_form(llm, ref):
            return False
    return True


def compare_lots_duration(llm_val: list[dict], ref_val: list[dict]):
    """Compare la durée des lots."""

    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    for ref_duree, llm_duree in zip(llm_val, ref_val):
        if isinstance(llm_duree, str) and isinstance(ref_duree, str):
            if llm_duree != ref_duree:
                return False
        elif isinstance(llm_duree, dict) and isinstance(ref_duree, dict):
            if not (
                llm_duree.get("duree_initiale") == ref_duree.get("duree_initiale")
                and llm_duree.get("duree_reconduction") == ref_duree.get("duree_reconduction")
                and llm_duree.get("nb_reconductions") == ref_duree.get("nb_reconductions")
                and llm_duree.get("delai_tranche_optionnelle") == ref_duree.get("delai_tranche_optionnelle")
            ):
                return False
        else:
            return False
    return True


def compare_contract_duration(llm_val: dict, ref_val: dict):
    """Compare la durée du marché."""
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


def compare_price_revision_formula(llm_val: str, ref_val: str):
    """Compare la formule de révision des prix."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    return False


def compare_reference_index(llm_val: str, ref_val: str):
    """Compare l'index de référence."""

    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    return False


def compare_advance_condition(llm_val: str, ref_val: str):
    """Compare les conditions d'avance CCAP."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    return False


def compare_price_revision(llm_val: str, ref_val: str):
    """Compare la révision des prix."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    return False


def compare_lots_amount(llm_val: list[dict], ref_val: list[dict]):
    """Compare les montants HT des lots."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    for montant_llm in llm_val:
        found = False
        for montant_ref in ref_val:
            if (
                montant_llm.get("numero_lot") == montant_ref.get("numero_lot")
                and montant_llm.get("montant_ht_maximum") == montant_ref.get("montant_ht_maximum")
                and montant_llm.get("type_montant") == montant_ref.get("type_montant")
            ):
                found = True
                break
        if not found:
            return False
    return True


def compare_amount(llm_val: str, ref_val: str):
    """Compare les montants HT."""
    if not llm_val and not ref_val:
        return True
    if not llm_val or not ref_val:
        return False

    return normalize_string(str(llm_val)) == normalize_string(str(ref_val))


def compare_global_contract(llm_val, ref_val):
    """Compare le CCAG."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    return normalize_string(str(llm_val)) == normalize_string(str(ref_val))


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
        "objet_marche": compare_contract_object,
        "forme_marche": compare_contract_form,
        "lots.*.titre": compare_lots_title,
        "lots.*.forme": compare_lots_contract_form,
        "lots.*.duree_lot": compare_lots_duration,
        "lots.*.montant_ht": compare_lots_amount,
        "duree_marche": compare_contract_duration,
        "formule_revision_prix": compare_price_revision_formula,
        "index_reference": compare_reference_index,
        "condition_avance": compare_advance_condition,
        "revision_prix": compare_price_revision,
        "montant_ht": compare_amount,
        "ccag": compare_global_contract,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""
    # Chemin vers le fichier CSV de test
    csv_path = CSV_DIR_PATH / "test_ccap.csv"

    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path)
    df_test.fillna("", inplace=True)
    for col in ("lots", "forme_marche", "duree_marche", "montant_ht", "pbm_ocr"):
        df_test[col] = df_test[col].apply(lambda x: json.loads(x))

    # Lancement du test
    return analyze_content_quality_test(df_test, "ccap", multi_line_coef=multi_line_coef, skip_clean=True)


df_test, df_result, df_merged = create_batch_test()


EXCLUDED_COLUMNS = ["objet_marche", "formule_revision_prix", "condition_avance", "revision_prix", "index_reference"]

comparison_functions = get_comparison_functions()

check_quality_one_field(df_merged, "lots.*.montant_ht", comparison_functions["lots.*.montant_ht"])

check_quality_one_row(df_merged, 18, comparison_functions)

check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
