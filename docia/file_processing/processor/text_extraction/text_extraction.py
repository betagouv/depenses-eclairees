"""
Orchestration de l'extraction de texte : dispatch selon le type de fichier
vers text_extract_document ou text_extract_excel.
"""

import logging
import re

from django.core.files.storage import default_storage

import tiktoken

from ..constants import DEFAULT_OCR_MODEL
from . import text_extract_document as document
from . import text_extract_excel as excel
from .data import TextExtractionResult

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


def count_words(text):
    """Compte le nombre de mots dans un texte"""
    if not text:
        return 0
    words = re.findall(r"\w+", text)
    return len(words)


def count_tokens(text):
    """Compte le nombre de tokens dans un texte"""
    if not text:
        return 0
    encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))


def clean_nul_bytes(text: str) -> str:
    """
    Clean NUL bytes (0x00) from text
    PostgreSQL doesn't allow NUL bytes in text fields.
    """
    return text.replace("\x00", "")


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
        tuple: (text, is_ocr, nb pages)
    """

    if not file_content:
        return "", False, None, None

    if file_type == "unknown":
        logger.warning(f"Unknown file type for {file_path} (type={file_type!r})")
        return "", False, None, None

    nb_pages = None

    # Excel
    if file_type == "xlsx":
        text, is_ocr = excel.extract_text_from_xlsx(file_content, file_path)
    elif file_type == "xls":
        text, is_ocr = excel.extract_text_from_xls(file_content, file_path)
    elif file_type == "ods":
        text, is_ocr = excel.extract_text_from_ods(file_content, file_path)
    # Documents (PDF, doc, docx, odt, txt, images)
    elif file_type == "pdf":
        text, is_ocr, nb_pages = document.extract_text_from_pdf(file_content, word_threshold, ocr_tool=ocr_tool)
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
    return text, is_ocr, nb_pages


def process_file(
    file_path: str,
    extension: str,
    word_threshold: int = 50,
    ocr_tool: str = "mistral-ocr",
) -> TextExtractionResult:
    """
    Extrait le texte d'un fichier (chemin + extension).

    Raises:
        UnsupportedFileType: si l'extension n'est pas supportée.
        FileNotFoundError: si le fichier n'existe pas.
    """
    if extension not in SUPPORTED_FILES_TYPE:
        raise UnsupportedFileType(f"Unsupported filed type {extension!r}")

    with default_storage.open(file_path, "rb") as f:
        file_content = f.read()

    text, is_ocr, nb_pages = extract_text(file_content, file_path, extension, word_threshold, ocr_tool=ocr_tool)

    nb_words = count_words(text)
    nb_tokens = count_tokens(text)

    return TextExtractionResult(
        text=text,
        is_ocr=is_ocr,
        model=DEFAULT_OCR_MODEL if is_ocr else None,
        nb_words=nb_words,
        nb_pages=nb_pages,
        nb_tokens=nb_tokens,
    )
