import io
from contextlib import contextmanager
from unittest.mock import patch

import pymupdf
from PIL import Image

from docia.file_processing.llm.client import LLMClient
from docia.file_processing.processor.text_extraction import extract_text_from_pdf
from tests.utils import bind_arguments

from .utils import ASSETS_DIR, assert_similar_text


@contextmanager
def patch_ocr_pdf(mock_function):
    """Context manager to patch LLMClient.ocr_pdf with proper argument binding."""
    with patch(
        "docia.file_processing.processor.text_extraction.text_extract_document.LLMClient.ocr_pdf",
        autospec=True,
        side_effect=mock_function,
    ) as mock_ocr_pdf:
        yield mock_ocr_pdf


def create_pdf_with_many_pages(num_pages=20, text_per_page="This is a test page."):
    """Create a PDF with many pages but small file size."""
    doc = pymupdf.Document()
    for _ in range(num_pages):
        page = doc.new_page()
        page.insert_text((50, 50), text_per_page)

    buff = io.BytesIO()
    doc.save(buff)
    doc.close()
    return buff.getvalue()


def create_pdf_with_big_images(num_images=5, image_size=(2000, 2000)):
    """Create a PDF with few pages but big file size (using images)."""
    doc = pymupdf.Document()

    # Create a big image
    big_image = Image.new("RGB", image_size, color="white")

    for _ in range(num_images):
        page = doc.new_page()

        # Convert PIL image to bytes and insert into PDF
        img_byte_arr = io.BytesIO()
        big_image.save(img_byte_arr, format="PNG")
        img_byte_arr.seek(0)

        # Insert image into PDF page
        rect = pymupdf.Rect(0, 0, image_size[0] / 10, image_size[1] / 10)  # Scale down for PDF
        page.insert_image(rect, stream=img_byte_arr.read())

    buff = io.BytesIO()
    doc.save(buff)
    doc.close()
    return buff.getvalue()


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

    with patch(
        "docia.file_processing.processor.text_extraction.text_extract_document.LLMClient.ocr_pdf", autospec=True
    ) as m:
        m.return_value = (expected_text, 1)
        text, is_ocr, nb_pages = extract_text_from_pdf(file_content)

    assert is_ocr
    assert nb_pages == 1
    assert_similar_text(text, 0.999)


def test_extract_text_from_pdf_many_pages():
    """Test extraction from PDF with many pages (small file size)."""
    # Create PDF with 20 pages (above the 15 page limit)
    file_total_pages = 20
    file_content = create_pdf_with_many_pages(num_pages=file_total_pages)

    # Mock
    batch_size = 3

    def mock_ocr_pdf(*args, **kwargs):
        bound_args = bind_arguments(LLMClient.ocr_pdf, *args, **kwargs)
        offset_pages = bound_args["offset_pages"]
        total_pages = bound_args["total_pages"]
        end_page = min(total_pages, offset_pages + batch_size)
        return "\n\n".join(
            f"PAGE {i}/{total_pages}" for i in range(offset_pages + 1, end_page + 1)
        ), end_page - offset_pages

    with patch_ocr_pdf(mock_ocr_pdf) as m_ocr_pdf:
        # Mock the OCR response for each batch
        text, is_ocr, nb_pages = extract_text_from_pdf(file_content)

    assert is_ocr
    assert nb_pages == 20
    assert text == "\n\n".join(f"PAGE {i}/20" for i in range(1, file_total_pages + 1))
    # Should have processed in batches due to page count
    assert len(m_ocr_pdf.call_args_list) == 7


def test_extract_text_from_pdf_big_file_size():
    """Test extraction from PDF with big file size (few pages)."""
    # Create PDF with big images (will exceed 5MB limit)
    file_total_pages = 3
    file_content = create_pdf_with_big_images(num_images=file_total_pages, image_size=(3000, 3000))

    # Mock
    batch_size = 3

    def mock_ocr_pdf(*args, **kwargs):
        bound_args = bind_arguments(LLMClient.ocr_pdf, *args, **kwargs)
        offset_pages = bound_args["offset_pages"]
        total_pages = bound_args["total_pages"]
        end_page = min(total_pages, offset_pages + batch_size)
        return "\n\n".join(
            f"BIG_PAGE {i}/{total_pages}" for i in range(offset_pages + 1, end_page + 1)
        ), end_page - offset_pages

    with patch_ocr_pdf(mock_ocr_pdf) as m_ocr_pdf:
        text, is_ocr, nb_pages = extract_text_from_pdf(file_content)

    assert is_ocr
    assert nb_pages == 3
    assert text == "\n\n".join(f"BIG_PAGE {i}/3" for i in range(1, file_total_pages + 1))
    # Should have processed in batches due to file size
    assert len(m_ocr_pdf.call_args_list) == 1


def test_extract_text_from_pdf_small_file():
    """Test extraction from small PDF (should not use batching)."""
    # Create small PDF (under 5MB and under 15 pages)
    file_total_pages = 5
    file_content = create_pdf_with_many_pages(num_pages=file_total_pages)

    # Mock
    def mock_ocr_pdf(*args, **kwargs):
        _bound_args = bind_arguments(LLMClient.ocr_pdf, *args, **kwargs)
        return "\n\n".join(
            f"SMALL_PAGE {i}/{file_total_pages}" for i in range(1, file_total_pages + 1)
        ), file_total_pages

    with patch_ocr_pdf(mock_ocr_pdf) as m_ocr_pdf:
        text, is_ocr, nb_pages = extract_text_from_pdf(file_content)

    assert is_ocr
    assert nb_pages == 5
    assert text == "\n\n".join(f"SMALL_PAGE {i}/5" for i in range(1, file_total_pages + 1))
    # Should have processed all at once (no batching)
    assert len(m_ocr_pdf.call_args_list) == 1
