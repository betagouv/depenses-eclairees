from app import extract_text_from_doc, extract_text_from_docx, extract_text_from_odt

from .utils import ASSETS_DIR, assert_similar_text


def test_extract_text_from_docx():
    with open(ASSETS_DIR / "lettre.docx", "rb") as f:
        file_content = f.read()

    text, is_ocr = extract_text_from_docx(file_content, "file.docx")
    assert not is_ocr
    assert_similar_text(text, 0.999)


def test_extract_text_from_odt():
    with open(ASSETS_DIR / "lettre.odt", "rb") as f:
        file_content = f.read()

    text, is_ocr = extract_text_from_odt(file_content, "file.odt")
    assert not is_ocr
    assert_similar_text(text, 0.90)


def test_extract_text_from_doc():
    with open(ASSETS_DIR / "lettre.doc", "rb") as f:
        file_content = f.read()

    text, is_ocr = extract_text_from_doc(file_content, "file.doc")
    assert not is_ocr
    assert_similar_text(text, 0.99)
