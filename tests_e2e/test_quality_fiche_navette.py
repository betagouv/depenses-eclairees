import json
import logging
import os
import sys

import django

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()


from tests_e2e.grist_api import get_data_from_grist  # noqa: E402
from tests_e2e.utils import (  # noqa: E402
    PROMPT_BENEFICIARY_ADMINISTRATION,
    PROMPT_OBJECT,
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_by_error_type,
    compare_normalized_string,
    compare_with_llm,
    get_fields_with_comparison_errors,
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
        "objet": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_OBJECT),
        "administration_beneficiaire": lambda a, e: compare_with_llm(a, e, prompt=PROMPT_BENEFICIARY_ADMINISTRATION),
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
        "fond": compare_normalized_string,
        "localisation_interministerielle": compare_normalized_string,
        "groupe_marchandise": compare_normalized_string,
        "axe_ministeriel_1": compare_normalized_string,
        "projet_analytique": compare_normalized_string,
        "localisation_ministerielle": compare_normalized_string,
        "axe_ministeriel_2": compare_normalized_string,
        "remarque": compare_normalized_string,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""

    df_test = get_data_from_grist(table="Fiche_navette_gt").query("commentaire == 'traité'")

    df_test.fillna("", inplace=True)

    # Lancement du test
    return analyze_content_quality_test(df_test, "fiche_navette", multi_line_coef=multi_line_coef)


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test()

    INCLUDED_COLUMNS = [
        "societe_principale",
        "accord_cadre",
        "id_accord_cadre",
        "montant_ht",
        "reconduction",
        "taux_tva",
        "centre_cout",
        "centre_financier",
        "activite",
        "domaine_fonctionnel",
        "fond",
        "localisation_interministerielle",
        "groupe_marchandise",
        "axe_ministeriel_1",
        "projet_analytique",
        "localisation_ministerielle",
        "axe_ministeriel_2",
    ]

    comparison_functions = get_comparison_functions()

    check_quality_by_error_type(df_merged, comparison_functions, mode="FP2", included_columns=INCLUDED_COLUMNS)

    check_global_statistics(df_merged, comparison_functions, included_columns=INCLUDED_COLUMNS)

    fields_with_errors = get_fields_with_comparison_errors(
        df_merged.sort_values(by="filename"), comparison_functions, included_columns=INCLUDED_COLUMNS
    )

    for v in fields_with_errors.values():
        print(json.dumps(v))
