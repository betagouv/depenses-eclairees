from unittest import mock

import pytest

from docia.file_processing.processor.extraction_text_from_attachments import (
    UnsupportedFileType,
    extract_text,
    extract_text_from_txt,
    process_file,
)

from .utils import ASSETS_DIR, assert_similar_text


def test_extract_text():
    file_content = b"content"

    with mock.patch(
        "docia.file_processing.processor.text_extraction.extract_pdf.extract_text_from_pdf", autospec=True
    ) as m:
        m.return_value = ("hello", True)
        extract_text(file_content, "file.pdf", "pdf")
        m.assert_called_once_with(file_content, 50, ocr_tool="mistral-ocr")

    with mock.patch(
        "docia.file_processing.processor.text_extraction.extract_pdf.extract_text_from_docx", autospec=True
    ) as m:
        m.return_value = ("hello", True)
        extract_text(file_content, "file.docx", "docx")
        m.assert_called_once_with(file_content, "file.docx")

    with mock.patch(
        "docia.file_processing.processor.text_extraction.extract_pdf.extract_text_from_txt", autospec=True
    ) as m:
        m.return_value = ("hello", True)
        extract_text(file_content, "file.txt", "txt")
        m.assert_called_once_with(file_content, "file.txt")

    with mock.patch(
        "docia.file_processing.processor.text_extraction.extract_pdf.extract_text_from_doc", autospec=True
    ) as m:
        m.return_value = ("hello", True)
        extract_text(file_content, "file.doc", "doc")
        m.assert_called_once_with(file_content, "file.doc")


@pytest.mark.parametrize("extension", ["png", "jpg", "jpeg", "tiff", "tif"])
def test_extract_text_from_image(extension):
    file_content = b"content"
    with mock.patch(
        "docia.file_processing.processor.text_extraction.extract_pdf.extract_text_from_image", autospec=True
    ) as m:
        m.return_value = ("hello", True)
        extract_text(file_content, f"file.{extension}", extension)
        m.assert_called_once_with(file_content, f"file.{extension}")


def test_extract_text_from_txt():
    with open(ASSETS_DIR / "lettre.md", "rb") as f:
        file_content = f.read()

    text, is_ocr = extract_text_from_txt(file_content, "file.md")
    assert not is_ocr
    assert_similar_text(text, 0.999)


def test_process_unsupported_file_type_raises():
    with pytest.raises(UnsupportedFileType):
        process_file("file.custom", "custom")
