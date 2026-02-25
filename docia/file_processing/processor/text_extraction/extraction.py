"""
Orchestration de l'extraction de texte : dispatch selon le type de fichier vers extract_pdf ou extract_excel.
"""

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed

from django.core.files.storage import default_storage
from tqdm import tqdm

import pandas as pd

from app.utils import clean_nul_bytes, count_words, getDate, log_execution_time

from . import extract_excel as excel
from . import extract_pdf as pdf

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


def display_pdf_stats(dfFiles, title="Statistiques globales"):
    """
    Affiche les statistiques sur les PDFs et l'OCR dans le dataframe.

    Args:
        dfFiles: DataFrame avec colonnes 'extension', 'is_OCR', 'nb_mot', etc.
        title: Titre pour les statistiques affichées.
    """
    print(f"\n{title}")
    print("=" * len(title))

    total_files = len(dfFiles)

    if "extension" in dfFiles.columns:
        pdf_count = dfFiles["extension"].apply(lambda x: x.lower() == "pdf").sum()
        pdf_percent = (pdf_count / total_files * 100) if total_files > 0 else 0
        print(f"Fichiers totaux: {total_files}")
        print(f"Fichiers PDF: {pdf_count} ({pdf_percent:.2f}%)")

    if "classification" in dfFiles.columns:
        devis_count = dfFiles["classification"].apply(lambda x: x == "devis").sum()
        devis_percent = (devis_count / total_files * 100) if total_files > 0 else 0
        print(f"Fichiers devis: {devis_count} ({devis_percent:.2f}%)")
        if "extension" in dfFiles.columns:
            pdf_devis_count = dfFiles[
                dfFiles["extension"].apply(lambda x: x.lower() == "pdf") & (dfFiles["classification"] == "devis")
            ].shape[0]
            pdf_devis_percent = (pdf_devis_count / total_files * 100) if total_files > 0 else 0
            print(f"Fichiers PDF et devis: {pdf_devis_count} ({pdf_devis_percent:.2f}%)")

    if "is_OCR" in dfFiles.columns:
        ocr_count = dfFiles["is_OCR"].sum()
        ocr_percent = (ocr_count / total_files * 100) if total_files > 0 else 0
        print("\nStatistiques OCR:")
        print(f"Fichiers traités par OCR: {ocr_count} ({ocr_percent:.2f}% du total)")
        if "is_pdf" in dfFiles.columns and dfFiles["is_pdf"].sum() > 0 and "extension" in dfFiles.columns:
            pdf_count = dfFiles["extension"].apply(lambda x: x.lower() == "pdf").sum()
            pdf_ocr_count = dfFiles[dfFiles["is_pdf"]]["is_OCR"].sum()
            pdf_ocr_percent = (pdf_ocr_count / pdf_count * 100) if pdf_count > 0 else 0
            print(f"PDFs traités par OCR: {pdf_ocr_count} ({pdf_ocr_percent:.2f}% des PDFs)")

    if "nb_mot" in dfFiles.columns and len(dfFiles) > 0:
        avg_words = dfFiles["nb_mot"].mean()
        median_words = dfFiles["nb_mot"].median()
        max_words = dfFiles["nb_mot"].max()
        min_words = dfFiles["nb_mot"].min()
        print("\nStatistiques nombre de mots:")
        print(f"Moyenne: {avg_words:.2f}")
        print(f"Médiane: {median_words:.2f}")
        print(f"Maximum: {max_words}")
        print(f"Minimum: {min_words}")

    print("=" * len(title))


def extract_text(
    file_content: bytes,
    file_path: str,
    file_type: str,
    word_threshold=50,
    ocr_tool: str = "mistral-ocr",
):
    """
    Extrait le texte d'un fichier selon son type.
    Délègue à extract_pdf (PDF, doc, docx, odt, txt, images) ou extract_excel (xlsx, xls, ods).

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

    # Formats actuels (PDF, documents, images)
    if file_type == "pdf":
        text, is_ocr = pdf.extract_text_from_pdf(file_content, word_threshold, ocr_tool=ocr_tool)
    elif file_type == "docx":
        text, is_ocr = pdf.extract_text_from_docx(file_content, file_path)
    elif file_type == "odt":
        text, is_ocr = pdf.extract_text_from_odt(file_content, file_path)
    elif file_type == "txt":
        text, is_ocr = pdf.extract_text_from_txt(file_content, file_path)
    elif file_type in ["png", "jpg", "jpeg", "tiff", "tif"]:
        text, is_ocr = pdf.extract_text_from_image(file_content, file_path)
    elif file_type == "doc":
        text, is_ocr = pdf.extract_text_from_doc(file_content, file_path)
    else:
        raise ValueError(f"Invalid file type for {file_path} (type={file_type!r})")

    text = clean_nul_bytes(text)
    return text, is_ocr


def df_extract_text(
    dfFiles: pd.DataFrame,
    word_threshold=50,
    ocr_tool: str = "mistral-ocr",
    save_path=None,
    directory_path=None,
    max_workers=4,
):
    """
    Traite le dataframe : extrait le texte de chaque fichier (extract_text), remplit text, is_OCR, nb_mot.
    """
    dfResult = dfFiles.copy(deep=False)
    dfResult["text"] = ""
    dfResult["is_OCR"] = False
    dfResult["nb_mot"] = 0

    print(f"\nTraitement de {len(dfResult)} fichiers...")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_df_row, row, word_threshold, ocr_tool)
            for row in dfResult.reset_index().to_dict("records")
        ]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Extraction du texte des fichiers (parallèle)"):
            idx, result = future.result()
            for key, value in result.items():
                dfResult.at[idx, key] = value

    display_pdf_stats(dfResult, "Statistiques finales après extraction de texte")
    try:
        if save_path and directory_path:
            full_save_path = f"{save_path}/textsExtraits_{directory_path.split('/')[-1]}_{getDate()}.csv"
            dfResult.to_csv(full_save_path, index=False)
            print(f"Liste des fichiers sauvegardées dans {full_save_path}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde du DataFrame : {e}")

    return dfResult


def process_df_row(row, word_threshold, ocr_tool: str = "mistral-ocr"):
    """Traite une ligne du DataFrame : extrait le texte et retourne (index, {text, is_OCR, nb_mot})."""
    filename = row["filename"]
    folder = row["dossier"]
    extension = row["extension"]
    file_path = f"{folder}/{filename}"

    try:
        text, is_ocr, nb_words = process_file(file_path, extension, word_threshold, ocr_tool=ocr_tool)
    except FileNotFoundError:
        logger.error("Erreur: Le fichier %s n'existe pas", file_path)
        text, is_ocr, nb_words = "", False, 0
    except Exception as e:
        logger.exception("Erreur lors de l'extraction du texte du fichier %s : %s", file_path, e)
        text, is_ocr, nb_words = "", False, 0

    return row["index"], {"text": text, "is_OCR": is_ocr, "nb_mot": nb_words}


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
