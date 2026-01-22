import json
import logging
import os
import re
import sys

import django
from django.conf import settings

import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from tests_e2e.utils import (  # noqa: E402
    analyze_content_quality_test,
    check_global_statistics,
    check_quality_one_field,
    check_quality_one_row,
    normalize_string, remove_accents,
)

logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()


def compare_iban(llm_val: str, ref_val: str):
    """Compare l'IBAN : comparaison des valeurs."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    llm_val = llm_val.replace(" ", "")
    ref_val = llm_val.replace(" ", "")
    return llm_val == ref_val


def compare_bic(llm_val: str, ref_val: str):
    """Compare le BIC : comparaison des valeurs."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    llm_val = llm_val.replace(" ", "")
    ref_val = llm_val.replace(" ", "")
    return llm_val == ref_val


def compare_bank(llm_val: str, ref_val: str):
    """Compare la banque : comparaison des valeurs."""

    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    llm_norm = normalize_string(llm_val)
    ref_norm = normalize_string(ref_val)

    if llm_norm == ref_norm:
        return True
    else:
        llm_norm_no_space = llm_norm.replace(" ", "")
        ref_norm_no_space = ref_norm.replace(" ", "")
        return llm_norm_no_space == ref_norm_no_space


def compare_account_owner(llm_val: str, ref_val: str):
    """Compare le titulaire du compte : comparaison des valeurs."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    llm_norm = normalize_string(llm_val)
    ref_norm = normalize_string(ref_val)

    if llm_norm == ref_norm:
        return True
    else:
        llm_norm_no_space = llm_norm.replace(" ", "")
        ref_norm_no_space = ref_norm.replace(" ", "")
        return llm_norm_no_space == ref_norm_no_space


def compare_address(llm_val: dict[str, str], ref_val: dict[str, str]):
    """Compare l'adresse : comparaison des valeurs selon la structure JSON.

    Structure attendue : {
        'numero_voie': 'le numéro de voie',
        'nom_voie': 'le nom de la voie',
        'complement_adresse': 'le complément d'adresse éventuel',
        'code_postal': 'le code postal',
        'ville': 'la ville',
        'pays': 'le pays'
    }
    """
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    # Liste des champs à comparer
    fields = ["numero_voie", "nom_voie", "complement_adresse", "code_postal", "ville", "pays"]

    # Comparer chaque champ
    for field in fields:
        llm_field_val = llm_val.get(field, "")
        ref_field_val = ref_val.get(field, "")

        # Normaliser les valeurs vides
        def _normalize(s):
            s = s.strip().upper()
            s = remove_accents(s)
            s = re.sub(r"[-']", " ", s)
            s = re.sub(r"\s\s", " ", s)
            return s
        llm_field_val = _normalize(llm_field_val)
        ref_field_val = _normalize(ref_field_val)

        # Comparer les valeurs du champ
        if llm_field_val != ref_field_val:
            return False

    return True


def compare_domiciliation(llm_val: str, ref_val: str):
    """Compare la domiciliation : comparaison des valeurs."""
    # Gestion des valeurs vides ou None
    if not llm_val and not ref_val:
        return True

    if not llm_val or not ref_val:
        return False

    return llm_val == ref_val


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
        "iban": compare_iban,
        "bic": compare_bic,
        "titulaire_compte": compare_account_owner,
        "adresse_postale_titulaire": compare_address,
        "domiciliation": compare_domiciliation,
        "banque": compare_bank,
    }


def create_batch_test(multi_line_coef=1):
    """Test de qualité des informations extraites par le LLM."""

    # Chemin vers le fichier CSV de test
    csv_path = CSV_DIR_PATH / "test_rib.csv"

    # Lecture du fichier CSV
    df_test = pd.read_csv(csv_path)
    df_test.fillna("", inplace=True)
    df_test["adresse_postale_titulaire"] = df_test["adresse_postale_titulaire"].apply(lambda x: json.loads(x))

    # Lancement du test
    return analyze_content_quality_test(df_test, "rib", multi_line_coef=multi_line_coef)


df_test, df_result, df_merged = create_batch_test()

comparison_functions = get_comparison_functions()

check_quality_one_field(df_merged, "iban", comparison_functions["iban"])
check_quality_one_field(df_merged, "titulaire_compte", comparison_functions["titulaire_compte"])
check_quality_one_field(df_merged, "adresse_postale_titulaire", comparison_functions["adresse_postale_titulaire"])

check_quality_one_row(df_merged, 26, comparison_functions)

check_global_statistics(df_merged, comparison_functions, excluded_columns=["domiciliation", "banque"])
