"""
Tests d'extraction Excel (XLSX, XLS, ODS) via le package text_extraction.
Utilise les assets générés par generate_excel_assets.py (plusieurs onglets, cellules fusionnées).
"""

import pytest

from docia.file_processing.processor.extraction_text_from_attachments import (
    extract_text_from_ods,
    extract_text_from_xls,
    extract_text_from_xlsx,
)

from .utils import ASSETS_DIR

# Contenu attendu dans les assets (generate_excel_assets.py)
MERGE_LEGEND_FRAGMENT = "Légende"
FEUILLE1 = "## Feuille1"
FEUILLE2 = "## Feuille2"
TITRE_FUSIONNE = "Titre fusionné"
SECTION = "Section"
TOTAL = "Total"


def test_extract_text_from_xlsx():
    """XLSX : 2 onglets (Feuille1, Feuille2), cellules fusionnées."""
    path = ASSETS_DIR / "sample.xlsx"
    if not path.exists():
        pytest.skip("sample.xlsx manquant. Exécuter generate_excel_assets.py.")
    with open(path, "rb") as f:
        content = f.read()
    text, is_ocr = extract_text_from_xlsx(content, str(path))
    assert not is_ocr
    assert MERGE_LEGEND_FRAGMENT in text
    assert FEUILLE1 in text
    assert FEUILLE2 in text
    assert TITRE_FUSIONNE in text
    assert SECTION in text
    assert TOTAL in text
    assert "|" in text


def test_extract_text_from_xls():
    """XLS : 2 onglets, cellules fusionnées."""
    path = ASSETS_DIR / "sample.xls"
    if not path.exists():
        pytest.skip("sample.xls manquant. Exécuter generate_excel_assets.py.")
    with open(path, "rb") as f:
        content = f.read()
    text, is_ocr = extract_text_from_xls(content, str(path))
    assert not is_ocr
    assert MERGE_LEGEND_FRAGMENT in text
    assert FEUILLE1 in text
    assert FEUILLE2 in text
    assert TITRE_FUSIONNE in text
    assert SECTION in text
    assert TOTAL in text
    assert "|" in text


def test_extract_text_from_ods():
    """ODS : 2 onglets, cellules fusionnées (pandas/odf peut représenter les fusions différemment)."""
    path = ASSETS_DIR / "sample.ods"
    if not path.exists():
        pytest.skip("sample.ods manquant. Exécuter generate_excel_assets.py.")
    with open(path, "rb") as f:
        content = f.read()
    text, is_ocr = extract_text_from_ods(content, str(path))
    assert not is_ocr
    assert MERGE_LEGEND_FRAGMENT in text
    assert FEUILLE1 in text
    assert FEUILLE2 in text
    assert "|" in text
    # Au moins une des données attendues (Titre fusionné peut être absente selon lecture odf des fusions)
    assert any(
        s in text for s in (TITRE_FUSIONNE, SECTION, TOTAL, "Ligne 1", "Col A", "V2", "V3", "Fin")
    )
