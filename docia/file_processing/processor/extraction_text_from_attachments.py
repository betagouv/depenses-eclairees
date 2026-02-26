"""
Façade de compatibilité : toute la logique d'extraction a été déplacée dans le package
docia.file_processing.processor.text_extraction (extraction.py, extract_pdf.py, extract_excel.py).
Ce module réexporte les symboles utilisés par le pipeline et les tests.
"""

from docia.file_processing.processor.text_extraction import (
    SUPPORTED_FILES_TYPE,
    UnsupportedFileType,
    df_extract_text,
    display_pdf_stats,
    extract_text,
    process_df_row,
    process_file,
)
from docia.file_processing.processor.text_extraction.extract_excel import (
    extract_text_from_ods,
    extract_text_from_xls,
    extract_text_from_xlsx,
)
from docia.file_processing.processor.text_extraction.extract_pdf import (
    extract_text_from_doc,
    extract_text_from_docx,
    extract_text_from_image,
    extract_text_from_odt,
    extract_text_from_pdf,
    extract_text_from_txt,
)

__all__ = [
    "SUPPORTED_FILES_TYPE",
    "UnsupportedFileType",
    "display_pdf_stats",
    "df_extract_text",
    "extract_text",
    "process_df_row",
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
