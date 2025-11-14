from app.processor import extract_text_from_pdf

from .utils import ASSETS_DIR, assert_similar_text


def test_extract_text_from_pdf():
    with open(ASSETS_DIR / "lettre.pdf", "rb") as f:
        file_content = f.read()

    text, is_ocr = extract_text_from_pdf(file_content, "file.pdf")
    assert not is_ocr
    assert_similar_text(text, 0.999)


def test_extract_text_from_pdf_ocr():
    with open(ASSETS_DIR / "lettre-ocr.pdf", "rb") as f:
        file_content = f.read()

    text, is_ocr = extract_text_from_pdf(file_content, "file.pdf")
    assert is_ocr
    assert_similar_text(text, 0.95)
