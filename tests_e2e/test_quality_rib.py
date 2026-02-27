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
    compare_address,
    compare_normalized_string,
)

logger = logging.getLogger("docia." + __name__)


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
        "iban": compare_normalized_string,
        "bic": compare_normalized_string,
        "titulaire_compte": compare_normalized_string,
        "adresse_postale_titulaire": compare_address,
        "domiciliation": compare_normalized_string,
        "banque": compare_normalized_string,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""

    df_test = get_data_from_grist(table="Rib_gt")
    df_test.fillna("", inplace=True)
    df_test["adresse_postale_titulaire"] = df_test["adresse_postale_titulaire"].apply(lambda x: json.loads(x))

    # Lancement du test
    return analyze_content_quality_test(df_test, "rib", multi_line_coef=multi_line_coef)


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test()

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, "iban", comparison_functions)
    check_quality_one_field(df_merged, "titulaire_compte", comparison_functions)
    check_quality_one_field(df_merged, "adresse_postale_titulaire", comparison_functions)

    check_quality_one_row(df_merged, 26, comparison_functions)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=["domiciliation", "banque"])
