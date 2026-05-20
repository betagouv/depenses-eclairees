import json
import logging
import os
import sys

import django

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()


from tests_e2e.grist_api import get_data_from_grist  # noqa: E402
from tests_e2e.test_quality_acte_engagement import compare_co_contractors  # noqa: E402
from tests_e2e.utils import (  # noqa: E402
    PROMPT_BENEFICIARY_ADMINISTRATION,
    PROMPT_OBJECT,
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_by_error_type,
    check_quality_one_field,
    compare_exact_string,
    compare_normalized_string,
    compare_with_llm,
    get_fields_with_comparison_errors,
)

logger = logging.getLogger("docia." + __name__)

_DATE_MARCHE_KEYS = ("duree_execution", "date_notification", "date_fin_execution")
_MONEY_BLOCK_KEYS = ("ht", "taux_tva", "tva", "ttc")


def compare_date_marche(actual, expected):
    """Compare date_marche : duree_execution, date_notification, date_fin_execution (chaînes)."""
    if not actual and not expected:
        return True
    if not actual or not expected:
        return False
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    for key in _DATE_MARCHE_KEYS:
        if actual.get(key) != expected.get(key):
            return False
    return True


def compare_money_block(actual, expected):
    """Compare montant_initial, montant_marche et incidence_financiere : ht, taux_tva, tva, ttc."""
    if not actual and not expected:
        return True
    if not actual or not expected:
        return False
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    for key in _MONEY_BLOCK_KEYS:
        if not compare_normalized_string(actual.get(key), expected.get(key)):
            return False
    return True


def get_comparison_functions():
    return {
        "numero_avenant": compare_exact_string,
        "administration_beneficiaire": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_BENEFICIARY_ADMINISTRATION),
        "societe_principale": compare_normalized_string,
        "siret_mandataire": compare_exact_string,
        "siren_mandataire": compare_exact_string,
        "cotraitants": compare_co_contractors,
        "objet_marche": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_OBJECT),
        "id_marche": compare_normalized_string,
        "date_marche": compare_date_marche,
        "montant_initial": compare_money_block,
        "montant_marche": compare_money_block,
        "objet_avenant": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_OBJECT),
        "incidence_bpu": compare_exact_string,
        "incidence_financiere": compare_money_block,
        "incidence_autre": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_OBJECT),
        "date_derniere_signature": compare_exact_string,
    }


def create_batch_test(multi_line_coef=1, max_workers=10, llm_model="mistral-medium-2508", debug_mode=False):
    """Test de qualité des informations extraites par le LLM pour les avenants."""

    df_test = get_data_from_grist(table="Avenant_gt").query("commentaire == 'traité'")

    if "nom_du_fichier" in df_test.columns and "filename" not in df_test.columns:
        df_test = df_test.rename(columns={"nom_du_fichier": "filename"})
    df_test = df_test.sort_values(by="filename").reset_index(drop=True)
    df_test.fillna("", inplace=True)

    for col in (
        "cotraitants",
        "date_marche",
        "montant_initial",
        "montant_marche",
        "incidence_financiere",
    ):
        if col in df_test.columns:
            df_test[col] = df_test[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)

    return analyze_content_quality_test(
        df_test,
        "avenant",
        multi_line_coef=multi_line_coef,
        max_workers=max_workers,
        llm_model=llm_model,
        debug_mode=debug_mode,
    )


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test(
        multi_line_coef=1, max_workers=30, debug_mode=True, llm_model="mistral-medium-2508"
    )

    INCLUDED_COLUMNS = [
        "numero_avenant",
        "societe_principale",
        "siret_mandataire",
        "siren_mandataire",
        "date_marche",
        "montant_initial",
        "montant_marche",
        "incidence_financiere",
        "date_derniere_signature",
    ]

    comparison_functions = get_comparison_functions()

    check_quality_by_error_type(df_merged, comparison_functions, mode="FP2", included_columns=INCLUDED_COLUMNS)

    check_quality_one_field(df_merged, "date_marche", comparison_functions, only_errors=True)

    check_global_statistics(df_merged, comparison_functions, included_columns=INCLUDED_COLUMNS)

    fields_with_errors = get_fields_with_comparison_errors(
        df_merged.sort_values(by="filename"), comparison_functions, included_columns=INCLUDED_COLUMNS
    )

    for v in fields_with_errors.values():
        print(json.dumps(v))
