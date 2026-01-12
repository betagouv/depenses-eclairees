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

from app.processor.analyze_content import LLMClient  # noqa: E402
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


def compare_batches(llm_val: list[dict[str, str]], ref_val: list[dict[str, str]]):
    """Compare les lots du marché."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    for lot_llm in llm_val:
        found = False
        for lot_ref in ref_val:
            if lot_llm.get("numero_lot") == lot_ref.get("numero_lot") and normalize_string(
                lot_llm.get("titre_lot")
            ) == normalize_string(lot_ref.get("titre_lot")):
                found = True
                break
        if not found:
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


def compare_compare_contract_form_batches(llm_val: list[dict], ref_val: list[dict]):
    """Compare la forme des lots du marché."""
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    for lot_llm in llm_val:
        found = False
        for lot_ref in ref_val:
            if lot_llm.get("numero_lot") == lot_ref.get("numero_lot"):
                llm_structure = lot_llm.get("structure")
                ref_structure = lot_ref.get("structure")
                llm_tranches = lot_llm.get("tranches")
                ref_tranches = lot_ref.get("tranches")
                llm_forme_prix = lot_llm.get("forme_prix")
                ref_forme_prix = lot_ref.get("forme_prix")
                if llm_structure == ref_structure and llm_tranches == ref_tranches and llm_forme_prix == ref_forme_prix:
                    found = True
                    break
                return False
        if not found:
            return False
    return True


def compare_batches_duration(llm_val: list[dict], ref_val: list[dict]):
    """Compare la durée des lots."""

    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    if len(llm_val) != len(ref_val):
        return False

    for duree_llm in llm_val:
        found = False
        for duree_ref in ref_val:
            if duree_llm.get("numero_lot") == duree_ref.get("numero_lot"):
                llm_duree = duree_llm.get("duree_lot")
                ref_duree = duree_ref.get("duree_lot")
                if isinstance(llm_duree, str) and isinstance(ref_duree, str):
                    if llm_duree == ref_duree:
                        found = True
                elif isinstance(llm_duree, dict) and isinstance(ref_duree, dict):
                    if (
                        llm_duree.get("duree_initiale") == ref_duree.get("duree_initiale")
                        and llm_duree.get("duree_reconduction") == ref_duree.get("duree_reconduction")
                        and llm_duree.get("nb_reconductions") == ref_duree.get("nb_reconductions")
                        and llm_duree.get("delai_tranche_optionnelle") == ref_duree.get("delai_tranche_optionnelle")
                    ):
                        found = True
                break
        if not found:
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


def compare_advance_conditions(llm_val: str, ref_val: str):
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


def compare_batches_amount(llm_val: list[dict], ref_val: list[dict]):
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


def compare_amounts(llm_val: str, ref_val: str):
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
        "lots": compare_batches,
        "forme_marche": compare_contract_form,
        "forme_marche_lots": compare_compare_contract_form_batches,
        "duree_lots": compare_batches_duration,
        "duree_marche": compare_contract_duration,
        "formule_revision_prix": compare_price_revision_formula,
        "index_reference": compare_reference_index,
        "condition_avance": compare_advance_conditions,
        "revision_prix": compare_price_revision,
        "montant_ht_lots": compare_batches_amount,
        "montant_ht": compare_amounts,
        "ccag": compare_global_contract,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""
    # Chemin vers le fichier CSV de test
    csv_path = CSV_DIR_PATH / "test_ccap.csv"

    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path)
    df_test.fillna("", inplace=True)
    df_test["lots"] = df_test["lots"].apply(lambda x: json.loads(x))
    df_test["forme_marche"] = df_test["forme_marche"].apply(lambda x: json.loads(x))
    df_test["forme_marche_lots"] = df_test["forme_marche_lots"].apply(lambda x: json.loads(x))
    df_test["duree_lots"] = df_test["duree_lots"].apply(lambda x: json.loads(x))
    df_test["duree_marche"] = df_test["duree_marche"].apply(lambda x: json.loads(x))
    df_test["montant_ht"] = df_test["montant_ht"].apply(lambda x: json.loads(x))
    df_test["montant_ht_lots"] = df_test["montant_ht_lots"].apply(lambda x: json.loads(x))

    # Lancement du test
    return analyze_content_quality_test(df_test, "ccap", multi_line_coef=multi_line_coef)


df_test, df_result, df_merged = create_batch_test()


EXCLUDED_COLUMNS = ["objet_marche", "formule_revision_prix", "condition_avance", "revision_prix", "index_reference"]

comparison_functions = get_comparison_functions()

check_quality_one_field(df_merged, "montant_ht_lots", comparison_functions["montant_ht_lots"])

check_quality_one_row(df_merged, 18, comparison_functions)

check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
