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
    compare_duration,
    compare_mandatee_bank_account,
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
        "administration_beneficiaire": lambda a, e: compare_with_llm(a, e, field="beneficiary_administration"),
        "objet_marche": lambda a, e: compare_with_llm(a, e, field="object"),
        "societe_principale": compare_normalized_string,
        "adresse_postale_titulaire": compare_address,
        "siret_titulaire": compare_normalized_string,
        "societe_sous_traitant": compare_normalized_string,
        "adresse_postale_sous_traitant": compare_address,
        "siret_sous_traitant": compare_normalized_string,
        "montant_sous_traitance_ht": compare_normalized_string,
        "montant_sous_traitance_ttc": compare_normalized_string,
        "description_prestations": compare_normalized_string,
        "date_signature": compare_normalized_string,
        "montant_tva": compare_normalized_string,
        "paiement_direct": compare_normalized_string,
        "rib_sous_traitant": compare_mandatee_bank_account,
        "conserve_avance": compare_normalized_string,
        "duree_sous_traitance": compare_duration,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""
    df_test = get_data_from_grist(table="Dc4_gt").query("commentaire == 'traité'")

    df_test.fillna("", inplace=True)
    for col in (
        "adresse_postale_titulaire",
        "adresse_postale_sous_traitant",
        "rib_sous_traitant",
        "duree_sous_traitance",
    ):
        df_test[col] = df_test[col].apply(lambda x: json.loads(x) if isinstance(x, str) else x)

    # Lancement du test
    return analyze_content_quality_test(df_test, "sous_traitance", multi_line_coef=multi_line_coef)


if __name__ == "__main__":
    df_test, df_result, df_merged = create_batch_test()

    EXCLUDED_COLUMNS = ["objet_marche", "administration_beneficiaire"]

    comparison_functions = get_comparison_functions()

    check_quality_one_field(df_merged, "rib_sous_traitant", comparison_functions)

    check_quality_one_row(df_merged, 0, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)

    check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
