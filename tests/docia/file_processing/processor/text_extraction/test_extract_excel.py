"""
Tests d'extraction Excel (XLSX, XLS, ODS) via le package text_extraction.
"""

import pytest

from docia.file_processing.processor.text_extraction import (
    extract_text_from_ods,
    extract_text_from_xls,
    extract_text_from_xlsx,
)
from docia.file_processing.processor.text_extraction.exceptions import FileSizeLimitException

from .utils import ASSETS_DIR

# Contenu attendu
EXPECTED_TEXT = (
    "## Feuille1\n"
    "\n"
    "|    | 0              | 1     |\n"
    "|---:|:---------------|:------|\n"
    "|  0 | Titre fusionné |       |\n"
    "|  1 | Col A          | Col B |\n"
    "|  2 | Ligne 1        | 10    |\n"
    "|  3 | Ligne 2        | 20    |\n"
    "|  4 | Total          |       |\n"
    "\n"
    "## Feuille2\n"
    "\n"
    "|    | 0       | 1   |\n"
    "|---:|:--------|:----|\n"
    "|  0 | Section | V1  |\n"
    "|  1 |         | V2  |\n"
    "|  2 |         | V3  |\n"
    "|  3 | Fin     |     |"
)


def _read_file(name):
    path = ASSETS_DIR / name
    with open(path, "rb") as f:
        content = f.read()
    return content, str(path)


def test_extract_text_from_xlsx():
    """XLSX : 2 onglets (Feuille1, Feuille2), cellules fusionnées."""
    content, path = _read_file("sample.xlsx")
    text, is_ocr = extract_text_from_xlsx(content, path)
    assert text == EXPECTED_TEXT
    assert not is_ocr


def test_extract_text_from_xls():
    """XLS : 2 onglets, cellules fusionnées."""
    content, path = _read_file("sample.xls")
    text, is_ocr = extract_text_from_xls(content, path)
    assert text == EXPECTED_TEXT
    assert not is_ocr


def test_extract_text_from_ods():
    """ODS : 2 onglets, cellules fusionnées (extraction stdlib ZIP+XML)."""
    content, path = _read_file("sample.ods")
    text, is_ocr = extract_text_from_ods(content, path)
    assert text == EXPECTED_TEXT
    assert not is_ocr


def test_extract_text_from_xlsx_size_limit():
    """Test that extract_text_from_xlsx raises ValueError when file_content exceeds size_limit."""
    content = b"1" * 200
    path = "test.xlsx"
    small_limit = 100  # Small limit for testing

    # Test that ValueError is raised
    with pytest.raises(FileSizeLimitException) as ex:
        extract_text_from_xlsx(content, path, size_limit=small_limit)
    assert str(ex.value) == "File is too large (200), limit=100"
