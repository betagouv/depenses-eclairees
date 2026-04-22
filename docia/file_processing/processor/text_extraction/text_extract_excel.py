"""
Extraction de texte depuis les fichiers Excel : xlsx, xls, ods.
Retourne un contenu markdown (tableaux avec |, légende des fusions, ## par feuille).
Sans pandas : listes Python + openpyxl (xlsx), xlrd (xls). ODS : stdlib uniquement (zip + XML).
"""

import io

import pandas as pd


def extract_text_from_xlsx(file_content: bytes, file_path: str = "", sep: str = "\n\n") -> tuple[str, bool]:
    """
    Extrait le texte (markdown) d'un fichier XLSX à partir de son contenu binaire.

    Args:
        file_content: Contenu du fichier .xlsx
        file_path: Chemin ou nom du fichier (pour les logs)
        sep: Séparateur entre les feuilles

    Returns:
        (texte markdown, False) — pas d'OCR pour Excel
    """
    sheets = pd.read_excel(io.BytesIO(file_content), dtype=str, header=None, sheet_name=None)
    parts = []
    for sheet_name, df in sheets.items():
        df = df.fillna("")
        md = df.to_markdown()
        if md:
            parts.append(f"## {sheet_name}\n\n{md}")
    return sep.join(parts), False


def extract_text_from_ods(file_content: bytes, file_path: str = "", sep: str = "\n\n") -> tuple[str, bool]:
    """
    Extrait le texte (markdown) d'un fichier ODS à partir de son contenu binaire.
    Utilise uniquement la stdlib : zipfile + xml.etree (pas de pandas ni odfpy).

    Returns:
        (texte markdown, False)
    """
    return extract_text_from_xlsx(file_content, file_path=file_path, sep=sep)


def extract_text_from_xls(file_content: bytes, file_path: str = "", sep: str = "\n\n") -> tuple[str, bool]:
    """
    Extrait le texte (markdown) d'un fichier XLS à partir de son contenu binaire.

    Returns:
        (texte markdown, False)
    """
    return extract_text_from_xlsx(file_content, file_path=file_path, sep=sep)
