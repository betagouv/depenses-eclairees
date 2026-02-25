"""
Extraction de texte depuis les pièces jointes (PDF, Office, images, Excel).
Réparti en extraction.py (orchestration), extract_pdf.py (formats actuels), extract_excel.py (xlsx, xls, ods).
"""

from docia.file_processing.processor.text_extraction.extraction import (
    SUPPORTED_FILES_TYPE,
    UnsupportedFileType,
    display_pdf_stats,
    df_extract_text,
    extract_text,
    process_df_row,
    process_file,
)

__all__ = [
    "SUPPORTED_FILES_TYPE",
    "UnsupportedFileType",
    "display_pdf_stats",
    "df_extract_text",
    "extract_text",
    "process_df_row",
    "process_file",
]
