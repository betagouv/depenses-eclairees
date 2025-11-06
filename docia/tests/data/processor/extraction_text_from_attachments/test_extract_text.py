from unittest import mock

import pytest

from app.processor.extraction_text_from_attachments import extract_text, extract_text_from_txt

from .utils import ASSETS_DIR, assert_similar_text


def test_extract_text():
    file_content = b"content"

    with mock.patch("app.processor.extraction_text_from_attachments.extract_text_from_pdf") as m:
        extract_text(file_content, "file.pdf", "pdf")
        m.assert_called_once_with(file_content, "file.pdf", 50)

    with mock.patch("app.processor.extraction_text_from_attachments.extract_text_from_docx") as m:
        extract_text(file_content, "file.docx", "docx")
        m.assert_called_once_with(file_content, "file.docx")

    with mock.patch("app.processor.extraction_text_from_attachments.extract_text_from_txt") as m:
        extract_text(file_content, "file.txt", "txt")
        m.assert_called_once_with(file_content, "file.txt")

    with mock.patch("app.processor.extraction_text_from_attachments.extract_text_from_doc") as m:
        extract_text(file_content, "file.doc", "doc")
        m.assert_called_once_with(file_content, "file.doc")


@pytest.mark.parametrize("extension", ["png", "jpg", "jpeg", "tiff", "tif"])
def test_extract_text_from_image(extension):
    file_content = b"content"
    with mock.patch("app.processor.extraction_text_from_attachments.extract_text_from_image") as m:
        extract_text(file_content, f"file.{extension}", extension)
        m.assert_called_once_with(file_content, f"file.{extension}")


def test_extract_text_from_txt():
    with open(ASSETS_DIR / "lettre.md", "rb") as f:
        file_content = f.read()

    text, is_ocr = extract_text_from_txt(file_content, "file.md")
    assert not is_ocr
    assert_similar_text(text, 0.999)
