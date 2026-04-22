"""
Tests d'extraction Excel (XLSX, XLS, ODS) via le package text_extraction.
Utilise les assets générés par generate_excel_assets.py (plusieurs onglets, cellules fusionnées).
"""

from docia.file_processing.processor.text_extraction import (
    extract_text_from_ods,
    extract_text_from_xls,
    extract_text_from_xlsx,
)
from docia.file_processing.processor.text_extraction.text_extract_excel import MERGE_LEGEND

from .utils import ASSETS_DIR

# Contenu attendu
TEXT_WITHOUT_CELL_MERGING = (
    "## Feuille1\n\n"
    "| Titre fusionné |  |\n"
    "| Col A | Col B |\n"
    "| Ligne 1 | 10 |\n"
    "| Ligne 2 | 20 |\n"
    "| Total |  |\n"
    "\n"
    "## Feuille2\n\n"
    "| Section | V1 |\n"
    "|  | V2 |\n"
    "|  | V3 |\n"
    "| Fin |  |"
)
TEXT_WITH_CELL_MERGING = (
    MERGE_LEGEND + "\n\n"
    "## Feuille1\n\n"
    "| Titre fusionné | # |\n"
    "| Col A | Col B |\n"
    "| Ligne 1 | 10 |\n"
    "| Ligne 2 | 20 |\n"
    "| Total |  |\n"
    "\n"
    "## Feuille2\n\n"
    "| Section | V1 |\n"
    "| # | V2 |\n"
    "| # | V3 |\n"
    "| Fin |  |"
)


def test_extract_text_from_xlsx():
    """XLSX : 2 onglets (Feuille1, Feuille2), cellules fusionnées."""
    path = ASSETS_DIR / "sample.xlsx"
    with open(path, "rb") as f:
        content = f.read()
    text, is_ocr = extract_text_from_xlsx(content, str(path))
    assert text == TEXT_WITHOUT_CELL_MERGING
    assert not is_ocr


def test_extract_text_from_xls():
    """XLS : 2 onglets, cellules fusionnées."""
    path = ASSETS_DIR / "sample.xls"
    with open(path, "rb") as f:
        content = f.read()
    text, is_ocr = extract_text_from_xls(content, str(path))
    assert text == TEXT_WITHOUT_CELL_MERGING
    assert not is_ocr


def test_extract_text_from_ods():
    """ODS : 2 onglets, cellules fusionnées (extraction stdlib ZIP+XML)."""
    path = ASSETS_DIR / "sample.ods"
    with open(path, "rb") as f:
        content = f.read()
    text, is_ocr = extract_text_from_ods(content, str(path))
    assert text == TEXT_WITH_CELL_MERGING
    assert not is_ocr
