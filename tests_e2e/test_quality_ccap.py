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
    PROMPT_OBJECT,
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_one_field,
    check_quality_one_row,
    compare_duration,
    compare_exact_string,
    compare_with_llm,
    get_fields_with_comparison_errors,
    normalize_string,
    get_fields_with_comparison_errors,
    compare_exact_string,
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
    llm_attributaires = llm_val.get("attributaires")
    ref_attributaires = ref_val.get("attributaires")

    return (
        llm_structure == ref_structure
        and llm_tranches == ref_tranches
        and llm_forme_prix == ref_forme_prix
        and llm_attributaires == ref_attributaires
    )


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
        "id_marche": compare_exact_string,
        "objet_marche": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_OBJECT),
        "forme_marche": compare_contract_form,
        "lots.*.titre": compare_lots_title,
        "lots.*.forme": compare_lots_contract_form,
        "lots.*.duree_lot": compare_lots_duration,
        "lots.*.montant_ht": compare_lots_amount,
        "duree_marche": compare_duration,
        "formule_revision_prix": compare_exact_string,
        "index_reference": compare_exact_string,
        "avance": compare_exact_string,
        "revision_prix": compare_exact_string,
        "montant_ht": compare_exact_string,
        "ccag": compare_exact_string,
        "mode_consultation": compare_exact_string,
        "regle_attribution_bc": compare_exact_string,
        "penalites": compare_exact_string,
        "code_cpv": compare_exact_string,
        "type_reconduction": compare_exact_string,
        "debut_execution": compare_exact_string,
        "retenue_garantie": compare_exact_string,
        "mois_zero_revision": compare_exact_string,
        "clause_sauvegarde_revision": compare_exact_string,
    }


def create_batch_test(multi_line_coef=1, max_workers=10, llm_model="openweight-medium", debug_mode=False):
    """Test de qualité des informations extraites par le LLM."""

    df_test = get_data_from_grist(table="Ccap_gt_v2")
    df_test = df_test.sort_values(by="filename").reset_index(drop=True)
    for col in (
        "lots",
        "forme_marche",
        "duree_marche",
        "montant_ht",
        "pbm_ocr",
        "avance",
        "penalites",
        "mode_consultation",
    ):
        df_test[col] = df_test[col].apply(lambda x: json.loads(x))

    # Lancement du test
    return analyze_content_quality_test(
        df_test,
        "ccap",
        multi_line_coef=multi_line_coef,
        max_workers=max_workers,
        llm_model=llm_model,
        debug_mode=debug_mode,
    )


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test(
        multi_line_coef=1, max_workers=10, llm_model="openweight-medium", debug_mode=True
    )

    EXCLUDED_COLUMNS = ["objet_marche"]

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, "avance", comparison_functions, only_errors=False)

    check_quality_one_row(df_merged, 18, comparison_functions)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

    fields_with_errors = get_fields_with_comparison_errors(
        df_merged.sort_values(by="filename"), comparison_functions, excluded_columns=EXCLUDED_COLUMNS
    )

    for v in fields_with_errors.values():
        print(json.dumps(v))



# "intro",
# "id_marche",
# "lots",
# "forme_marche",
# "forme_marche_lots",
# "duree_marche",
# "duree_lots",
# "montant_ht",
# "montant_ht_lots",
# "ccag",
# "condition_avance",
# "formule_revision_prix", ------ schema de données ne va pas
# "index_reference", ---- standardiser schema de données
# "revision_prix",
# "mode_consultation",  ---- standardiser schema de données
# "regle_attribution_bc", -- modif prompt ajouter lots
# "type_reconduction", -- bcp d'erreurs llm
# "debut_execution", --- bcp d'erreurs llm
# "retenue_garantie", -- OK
# "mois_zero",
# "clause_sauvegarde_revision", -- bcp d'erreurs llm
# "delai_execution_bc_ms", -- trop d'erreurs llm
# "penalites",
# "code_cpv"