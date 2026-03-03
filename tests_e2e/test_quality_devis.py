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
    compare_exact_string,
    compare_with_llm,
    get_fields_with_comparison_errors,
)

logger = logging.getLogger("docia." + __name__)


def get_comparison_functions():
    return {
        "numero_devis": compare_exact_string,
        "objet": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_OBJECT),
        "date_emission": compare_exact_string,
        "titulaire": compare_exact_string,
        "administration_beneficiaire": compare_exact_string,
        "prestations": compare_exact_string,
        "montants": compare_exact_string,
        "duree_validite": compare_exact_string,
        "date_signature": compare_exact_string,
        "dernier_signataire": compare_exact_string
    }

def create_batch_test(multi_line_coef=1, max_workers=10, llm_model="openweight-medium", debug_mode=False):
    """Test de qualité des informations extraites par le LLM."""

    df_test = get_data_from_grist(table="Devis_gt")
    df_test = df_test.sort_values(by="filename").reset_index(drop=True)
    for col in (
        "titulaire",
        "prestations",
        "montants",
    ):
        df_test[col] = df_test[col].apply(lambda x: json.loads(x))

    # Lancement du test
    return analyze_content_quality_test(
        df_test.iloc[0:6],
        "devis",
        multi_line_coef=multi_line_coef,
        max_workers=max_workers,
        llm_model=llm_model,
        debug_mode=debug_mode,
    )

if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test(
        multi_line_coef=1, max_workers=30, debug_mode=True, llm_model="openweight-small"
    )

    EXCLUDED_COLUMNS = ["objet"]

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, "objet", comparison_functions, only_errors=False)

    check_quality_one_row(df_merged, 1, comparison_functions)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

    fields_with_errors = get_fields_with_comparison_errors(
        df_merged.sort_values(by="filename"), comparison_functions, excluded_columns=EXCLUDED_COLUMNS
    )

    for v in fields_with_errors.values():
        print(json.dumps(v))