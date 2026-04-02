from unittest.mock import patch

from docia.file_processing.processor.text_extraction import extract_text_from_pdf

from .utils import ASSETS_DIR, assert_similar_text


def test_extract_text_from_pdf():
    with open(ASSETS_DIR / "lettre.pdf", "rb") as f:
        file_content = f.read()

    with open(ASSETS_DIR / "lettre.md", "r") as f:
        expected_text = f.read()

    with patch(
        "docia.file_processing.processor.text_extraction.text_extract_document.LLMClient.ocr_pdf", autospec=True
    ) as m:
        m.return_value = (expected_text, 1)
        text, is_ocr, nb_pages = extract_text_from_pdf(file_content)

    assert is_ocr
    assert nb_pages == 1
    assert_similar_text(text, 0.999)


def test_extract_text_from_pdf_ocr():
    with open(ASSETS_DIR / "lettre-ocr.pdf", "rb") as f:
        file_content = f.read()
    with open(ASSETS_DIR / "lettre.md", "r") as f:
        expected_text = f.read()

    with patch("docia.file_processing.processor.text_extraction.text_extract_document.LLMClient") as mock_llm_class:
        mock_llm_class.return_value.ocr_pdf.return_value = (expected_text, 1)
        text, is_ocr, nb_pages = extract_text_from_pdf(file_content)

    assert is_ocr
    assert nb_pages == 1
    assert_similar_text(text, 0.999)
