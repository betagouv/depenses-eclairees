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
    compare_normalized_string,
    compare_with_llm,
)

logger = logging.getLogger("docia." + __name__)


def get_comparison_functions():
    """Mapping des colonnes vers leurs fonctions de comparaison

    Retourne le dictionnaire des fonctions de comparaison.
    Cette fonction garantit que les références pointent toujours vers les dernières versions des fonctions,
    même après un rechargement de module.

    Returns:
        dict: Dictionnaire associant les noms de colonnes à leurs fonctions de comparaison
    """
    return {
        "objet": lambda a, e: compare_with_llm(a, e, field="object"),
        "administration_beneficiaire": lambda a, e: compare_with_llm(a, e, field="beneficiary_administration"),
        "societe_principale": compare_normalized_string,
        "accord_cadre": compare_normalized_string,
        "id_accord_cadre": compare_normalized_string,
        "montant_ht": compare_normalized_string,
        "reconduction": compare_normalized_string,
        "taux_tva": compare_normalized_string,
        "centre_cout": compare_normalized_string,
        "centre_financier": compare_normalized_string,
        "activite": compare_normalized_string,
        "domaine_fonctionnel": compare_normalized_string,
        "localisation_interministerielle": compare_normalized_string,
        "groupe_marchandise": compare_normalized_string,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""

    df_test = get_data_from_grist(table="Fiche_navette_gt").query("commentaire == 'traité'")

    df_test.fillna("", inplace=True)

    # Lancement du test
    return analyze_content_quality_test(df_test, "fiche_navette", multi_line_coef=multi_line_coef)


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test()

    EXCLUDED_COLUMNS = ["objet", "administration_beneficiaire"]

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, "groupe_marchandise", comparison_functions)

    check_quality_one_row(df_merged, 0, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
