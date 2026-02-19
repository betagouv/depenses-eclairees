import json
import logging
import os
import sys

import django

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()


from app.grist.grist_api import get_data_from_grist  # noqa: E402
from tests_e2e.utils import (  # noqa: E402
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_one_field,
    check_quality_one_row,
    compare_duration,
    compare_with_llm,
    normalize_string,
)

logger = logging.getLogger("docia." + __name__)


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
        "objet_marche": lambda a, e: compare_with_llm(a, e, field="object"),
        "forme_marche": compare_contract_form,
        "lots.*.titre": compare_lots_title,
        "lots.*.forme": compare_lots_contract_form,
        "lots.*.duree_lot": compare_lots_duration,
        "lots.*.montant_ht": compare_lots_amount,
        "duree_marche": compare_duration,
        "formule_revision_prix": compare_price_revision_formula,
        "index_reference": compare_reference_index,
        "condition_avance": compare_advance_condition,
        "revision_prix": compare_price_revision,
        "montant_ht": compare_amount,
        "ccag": compare_global_contract,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""

    df_test = get_data_from_grist(table="Ccap_gt_v2")
    df_test.fillna("", inplace=True)
    for col in ("lots", "forme_marche", "duree_marche", "montant_ht", "pbm_ocr"):
        df_test[col] = df_test[col].apply(lambda x: json.loads(x))

    # Lancement du test
    return analyze_content_quality_test(df_test.iloc[0:5], "ccap", multi_line_coef=multi_line_coef)


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test()

    EXCLUDED_COLUMNS = ["objet_marche", "formule_revision_prix", "condition_avance", "revision_prix", "index_reference"]

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, "lots.*.montant_ht", comparison_functions)

    check_quality_one_row(df_merged, 18, comparison_functions)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
