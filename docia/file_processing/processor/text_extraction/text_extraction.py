"""
Orchestration de l'extraction de texte : dispatch selon le type de fichier
vers text_extract_document ou text_extract_excel.
"""

import logging

from django.core.files.storage import default_storage

from app.utils import clean_nul_bytes, count_words, log_execution_time

from . import text_extract_document as document
from . import text_extract_excel as excel

logger = logging.getLogger("docia." + __name__)


class UnsupportedFileType(Exception):
    pass


SUPPORTED_FILES_TYPE = [
    "doc",
    "docx",
    "odt",
    "pdf",
    "txt",
    "jpg",
    "jpeg",
    "png",
    "tiff",
    "tif",
    "xlsx",
    "xls",
    "ods",
]


def extract_text(
    file_content: bytes,
    file_path: str,
    file_type: str,
    word_threshold=50,
    ocr_tool: str = "mistral-ocr",
):
    """
    Extrait le texte d'un fichier selon son type.
    Délègue à text_extract_document (PDF, doc, docx, odt, txt, images) ou text_extract_excel (xlsx, xls, ods).

    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """
    if not file_content:
        return "", False

    if file_type == "unknown":
        logger.warning(f"Unknown file type for {file_path} (type={file_type!r})")
        return "", False

    # Excel
    if file_type == "xlsx":
        return excel.extract_text_from_xlsx(file_content, file_path)
    if file_type == "xls":
        return excel.extract_text_from_xls(file_content, file_path)
    if file_type == "ods":
        return excel.extract_text_from_ods(file_content, file_path)

    # Documents (PDF, doc, docx, odt, txt, images)
    if file_type == "pdf":
        text, is_ocr = document.extract_text_from_pdf(file_content, word_threshold, ocr_tool=ocr_tool)
    elif file_type == "docx":
        text, is_ocr = document.extract_text_from_docx(file_content, file_path)
    elif file_type == "odt":
        text, is_ocr = document.extract_text_from_odt(file_content, file_path)
    elif file_type == "txt":
        text, is_ocr = document.extract_text_from_txt(file_content, file_path)
    elif file_type in ["png", "jpg", "jpeg", "tiff", "tif"]:
        text, is_ocr = document.extract_text_from_image(file_content, file_path)
    elif file_type == "doc":
        text, is_ocr = document.extract_text_from_doc(file_content, file_path)
    else:
        raise ValueError(f"Invalid file type for {file_path} (type={file_type!r})")

    text = clean_nul_bytes(text)
    return text, is_ocr


def process_file(
    file_path: str,
    extension: str,
    word_threshold: int = 50,
    ocr_tool: str = "mistral-ocr",
):
    """
    Extrait le texte d'un fichier (chemin + extension).

    Returns:
        tuple: (texte, is_ocr, nb_mots)

    Raises:
        UnsupportedFileType: si l'extension n'est pas supportée.
        FileNotFoundError: si le fichier n'existe pas.
    """
    if extension not in SUPPORTED_FILES_TYPE:
        raise UnsupportedFileType(f"Unsupported filed type {extension!r}")

    with default_storage.open(file_path, "rb") as f:
        file_content = f.read()

    with log_execution_time(f"extract_text({file_path})"):
        text, is_ocr = extract_text(file_content, file_path, extension, word_threshold, ocr_tool=ocr_tool)

    nb_words = count_words(text)
    return text, is_ocr, nb_words
