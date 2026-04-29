import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import django
from django.conf import settings

from tqdm import tqdm

import pandas as pd

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from app.grist import get_data_from_grist  # noqa: E402

from docia.file_processing.llm.client import LLMClient  # noqa: E402
from tests_e2e.test_quality_acte_engagement import get_comparison_functions  # noqa: E402
from tests_e2e.utils import (  # noqa: E402
    analyze_content_quality_test,
    check_global_statistics,
)

logger = logging.getLogger("docia." + __name__)

PROJECT_PATH = settings.BASE_DIR
CSV_DIR_PATH = (PROJECT_PATH / ".." / "data" / "test").resolve()
ASSETS_DIR = CSV_DIR_PATH / "assets"


def _ocr_one(idx_filename: tuple[int, str]) -> str:
    idx, filename = idx_filename
    client = LLMClient()
    file_path = ASSETS_DIR / filename
    if not file_path.exists():
        logger.warning("Fichier absent: %s", file_path)
        return ""
    try:
        pdf_content = file_path.read_bytes()
        text, nb_pages = client.ocr_pdf(pdf_content)
        return text or ""
    except Exception as e:
        logger.exception("Erreur OCR pour %s: %s", filename, e)
        return ""


def extract_texts_via_ocr(df_test: pd.DataFrame, max_workers: int = 4) -> list[str]:
    """
    Pour chaque ligne du dataframe, charge le PDF depuis data/test/assets
    et extrait le texte via LLMClient.ocr_pdf (en parallèle).

    Returns:
        Liste des textes extraits (un par ligne, dans le même ordre).
    """
    items = [(i, row.get("filename", "")) for i, row in df_test.iterrows()]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        texts = list(
            tqdm(
                executor.map(_ocr_one, items),
                total=len(items),
                desc="OCR",
                unit="doc",
            )
        )
    return texts


def create_batch_test_ocr(multi_line_coef=1):
    """
    Charge test_ocr.csv (documents acte_engagement), extrait le texte via OCR
    pour chaque fichier dans data/test/assets, puis lance le test de qualité
    comme test_quality_acte_engagement.
    """
    df_test = get_data_from_grist(table="Acte_engagement_gt").query("commentaire == 'traité'")
    df_test["montant_ht"] = df_test["montant_ht"].apply(lambda x: f"{float(x):.2f}" if x else "")
    df_test["montant_ttc"] = df_test["montant_ttc"].apply(lambda x: f"{float(x):.2f}" if x else "")
    df_test["montant_tva"] = df_test["montant_tva"].apply(lambda x: f"{float(x):.2f}" if x else "")
    df_test["rib_mandataire"] = df_test["rib_mandataire"].apply(lambda x: json.loads(x))
    df_test["cotraitants"] = df_test["cotraitants"].apply(lambda x: json.loads(x))
    df_test["sous_traitants"] = df_test["sous_traitants"].apply(lambda x: json.loads(x))
    df_test["duree"] = df_test["duree"].apply(lambda x: json.loads(x))
    df_test["rib_autres"] = df_test["rib_autres"].apply(lambda x: json.loads(x))
    df_test["montants_en_annexe"] = df_test["montants_en_annexe"].apply(lambda x: json.loads(x))
    df_test["forme_marche"] = df_test["forme_marche"].apply(lambda x: json.loads(x))

    # Étape d'extraction de texte via l'API OCR (absent dans test_quality_acte_engagement)
    logger.info("Extraction du texte via OCR pour %d document(s)...", len(df_test))
    df_test["text"] = extract_texts_via_ocr(df_test)

    return analyze_content_quality_test(df_test, "acte_engagement", multi_line_coef=multi_line_coef)


EXCLUDED_COLUMNS = ["objet_marche", "administration_beneficiaire", "avance"]
MIN_GLOBAL_ACCURACY = 0.88


def test_ocr_quality_global_accuracy():
    """L'accuracy globale du test OCR (acte_engagement) doit dépasser 88%."""
    df_test, df_result, df_merged = create_batch_test_ocr()
    comparison_functions = get_comparison_functions()
    global_accuracy = check_global_statistics(df_merged, comparison_functions, excluded_columns=EXCLUDED_COLUMNS)
    assert global_accuracy > MIN_GLOBAL_ACCURACY, f"Accuracy globale {global_accuracy:.2%} <= {MIN_GLOBAL_ACCURACY:.0%}"


if __name__ == "__main__":
    test_ocr_quality_global_accuracy()
