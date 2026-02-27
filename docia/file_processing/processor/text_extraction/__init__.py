"""
Extraction de texte depuis les pièces jointes (PDF, Office, images, Excel).
Réparti en text_extraction.py (orchestration), text_extract_document.py (documents),
text_extract_excel.py (xlsx, xls, ods).
"""

from docia.file_processing.processor.text_extraction.text_extract_document import (
    extract_text_from_doc,
    extract_text_from_docx,
    extract_text_from_image,
    extract_text_from_odt,
    extract_text_from_pdf,
    extract_text_from_txt,
)
from docia.file_processing.processor.text_extraction.text_extract_excel import (
    extract_text_from_ods,
    extract_text_from_xls,
    extract_text_from_xlsx,
)
from docia.file_processing.processor.text_extraction.text_extraction import (
    SUPPORTED_FILES_TYPE,
    UnsupportedFileType,
    extract_text,
    process_file,
)

__all__ = [
    "SUPPORTED_FILES_TYPE",
    "UnsupportedFileType",
    "extract_text",
    "process_file",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "extract_text_from_odt",
    "extract_text_from_txt",
    "extract_text_from_image",
    "extract_text_from_doc",
    "extract_text_from_xlsx",
    "extract_text_from_xls",
    "extract_text_from_ods",
]
