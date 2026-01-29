import io
import logging
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed

from django.core.files.storage import default_storage

import docx2txt
import pymupdf
import tesserocr
from PIL import Image
from tqdm import tqdm

import pandas as pd

from app.data.sql.sql import bulk_update_attachments
from app.grist import API_KEY_GRIST, URL_TABLE_ATTACHMENTS, update_records_in_grist
from app.utils import clean_nul_bytes, count_words, getDate, log_execution_time
from docia.file_processing.llm.client import LLMClient
from docia.file_processing.processor.pdf_drawings import add_drawings_to_pdf

logger = logging.getLogger("docia." + __name__)


class UnsupportedFileType(Exception):
    pass


SUPPORTED_FILES_TYPE = [
    "docdocx",
    "odt",
    "pdf",
    "txt",
    "jpg",
    "jpeg",
    "png",
    "tiff",
    "tif",
]


# Fonction pour afficher les statistiques sur les PDFs et l'OCR
def display_pdf_stats(dfFiles, title="Statistiques globales"):
    """
    Affiche les statistiques sur les PDFs et l'OCR dans le dataframe

    Args:
        df (DataFrame): DataFrame avec les colonnes 'is_pdf' et potentiellement 'is_OCR'
        title (str): Titre pour les statistiques affichées
    """
    print(f"\n{title}")
    print("=" * len(title))

    # Statistiques sur les PDFs
    total_files = len(dfFiles)

    if "extension" in dfFiles.columns:
        pdf_count = dfFiles["extension"].apply(lambda x: x.lower() == "pdf").sum()
        pdf_percent = (pdf_count / total_files * 100) if total_files > 0 else 0

        print(f"Fichiers totaux: {total_files}")
        print(f"Fichiers PDF: {pdf_count} ({pdf_percent:.2f}%)")

    # Statistiques sur les devis (si la colonne existe)
    if "classification" in dfFiles.columns:
        devis_count = dfFiles["classification"].apply(lambda x: x == "devis").sum()
        devis_percent = (devis_count / total_files * 100) if total_files > 0 else 0

        print(f"Fichiers devis: {devis_count} ({devis_percent:.2f}%)")

        # Fichiers qui sont à la fois PDF et devis
        if "extension" in dfFiles.columns:
            pdf_devis_count = dfFiles[
                dfFiles["extension"].apply(lambda x: x.lower() == "pdf") & (dfFiles["classification"] == "devis")
            ].shape[0]
            pdf_devis_percent = (pdf_devis_count / total_files * 100) if total_files > 0 else 0

            print(f"Fichiers PDF et devis: {pdf_devis_count} ({pdf_devis_percent:.2f}%)")

    # Statistiques sur l'OCR (si la colonne existe)
    if "is_OCR" in dfFiles.columns:
        ocr_count = dfFiles["is_OCR"].sum()
        ocr_percent = (ocr_count / total_files * 100) if total_files > 0 else 0

        print("\nStatistiques OCR:")
        print(f"Fichiers traités par OCR: {ocr_count} ({ocr_percent:.2f}% du total)")

        # Si nous avons aussi des informations sur les PDFs
        if "is_pdf" in dfFiles.columns and dfFiles["is_pdf"].sum() > 0:
            pdf_ocr_count = dfFiles[dfFiles["is_pdf"]]["is_OCR"].sum()
            pdf_ocr_percent = (pdf_ocr_count / pdf_count * 100) if pdf_count > 0 else 0

            print(f"PDFs traités par OCR: {pdf_ocr_count} ({pdf_ocr_percent:.2f}% des PDFs)")

    # Statistiques sur le nombre de mots (si la colonne existe)
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


def extract_text_from_pdf(file_content: bytes, word_threshold=50):
    """
    Extrait le texte d'un PDF. Si le PDF contient moins de mots que le seuil défini,
    utilise l'OCR pour extraire le texte.

    Args:
        file_content (bytes): Contenu du fichier
        word_threshold (int): Nombre minimal de mots en dessous duquel l'OCR est utilisé
        folder (str): Dossier contenant les fichiers PDF

    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """
    doc = pymupdf.Document(stream=file_content)

    # Essayer d'extraire directement le texte dans l'ordre vertical
    text = "\n".join([page.get_text(sort=True) for page in doc]).strip()
    is_ocr_used = False

    # Compter les mots dans le texte extrait
    word_count = count_words(text)

    # Si suffisamment de mots, c'est un pdf natif
    if word_count >= word_threshold:
        doc_with_drawings = add_drawings_to_pdf(doc)
        text = "\n".join([page.get_text(sort=True) for page in doc_with_drawings]).strip()

    # Si peu de mots sont extraits, c'est peut-être une image scannée
    # Utilisation de l'API OCR (Albert / OpenGateLLM)
    else:
        is_ocr_used = True
        llm_client = LLMClient()
        text = llm_client.ocr_pdf(file_content)

    return text, is_ocr_used


def extract_text_from_docx(file_content: bytes, file_path: str):
    """
    Extrait le texte d'un fichier DOCX avec gestion d'erreurs robuste.

    Args:
        file_content (bytes): Contenu du fichier
        file_path (str): Chemin du fichier DOCX

    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """

    try:
        # Tentative d'extraction du texte avec docx2txt
        text = docx2txt.process(io.BytesIO(file_content))

        # Vérifier que le texte a été extrait
        if text is None:
            print(f"Attention: Aucun texte extrait de {file_path}")
            return "", False

        # Nettoyer le texte extrait
        text = text.strip()

        # Vérifier que le texte n'est pas vide après nettoyage
        if not text:
            print(f"Attention: Le fichier {file_path} ne contient pas de texte lisible")
            return "", False

        return text, False

    except FileNotFoundError:
        print(f"Erreur: Fichier {file_path} introuvable")
        return "", False

    except PermissionError:
        print(f"Erreur: Permission refusée pour lire le fichier {file_path}")
        return "", False

    except OSError as e:
        print(f"Erreur système lors de la lecture de {file_path}: {e}")
        return "", False

    except Exception as e:
        # try: # Si la lecture en docx échoue, on essaye de convertir en pdf et d'extraire le texte
        #     extension_original = '.' + file_path.split(".")[-1]
        #     os.rename(file_path, file_path.replace(extension_original, ".pdf"))
        #     filename_pdf = filename.replace(extension_original, ".pdf")
        #     text, is_ocr = extract_text_from_pdf(filename_pdf, folder)
        #     os.rename(file_path.replace(extension_original, ".pdf"), file_path)
        #     return text, is_ocr
        # except Exception as e:
        print(f"Erreur inattendue lors de l'extraction du texte de {file_path}: {e}")
        return "", False


def extract_text_from_odt(file_content: bytes, file_path: str):
    """
    Extrait le texte d'un fichier ODT avec gestion d'erreurs robuste.

    Args:
        file_content (bytes): Contenu du fichier
        file_path (str): Nom du fichier ODT

    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """

    try:
        # Méthode 1: Essayer avec zipfile (ODT est un fichier ZIP)
        try:
            with zipfile.ZipFile(io.BytesIO(file_content), "r") as zip_file:
                # Lire le contenu XML principal
                if "content.xml" in zip_file.namelist():
                    content = zip_file.read("content.xml")
                    # Parser le XML pour extraire le texte
                    root = ET.fromstring(content)

                    # Extraire tout le texte des éléments
                    text_parts = []
                    for elem in root.iter():
                        if elem.text:
                            text_parts.append(elem.text.strip())

                    text = "\n".join([part for part in text_parts if part])
                    if text and text.strip():
                        return text.strip(), False
        except Exception as e:
            # try: # Si la lecture en odt échoue, on essaye de convertir en pdf et d'extraire le texte
            #     extension_original = '.' + file_path.split(".")[-1]
            #     os.rename(file_path, file_path.replace(extension_original, ".pdf"))
            #     filename_pdf = filename.replace(extension_original, ".pdf")
            #     text, is_ocr = extract_text_from_pdf(filename_pdf, folder)
            #     os.rename(file_path.replace(extension_original, ".pdf"), file_path)
            #     return text, is_ocr
            # except Exception as e:
            print(f"zipfile ne peut pas traiter {file_path}: {e}")
            return "", False

        # Si l'extraction échoue
        print(f"Impossible d'extraire le texte de {file_path}")
        return "", False

    except Exception as e:
        print(f"Erreur inattendue lors de l'extraction du texte de {file_path}: {e}")
        return "", False


def extract_text_from_txt(file_content: bytes, file_path: str):
    """
    Extrait le texte d'un fichier TXT avec gestion d'erreurs robuste.
    """

    try:
        # Lire le contenu du fichier
        text = file_content.decode("utf-8", errors="ignore")
        return text, False
    except Exception as e:
        print(f"Erreur inattendue lors de l'extraction du texte de {file_path}: {e}")
        return "", False


def extract_text_from_image(file_content: bytes, file_path: str):
    """
    Extrait le texte d'une image (PNG, JPG, JPEG, TIFF) avec OCR (Optical Character Recognition).

    Args:
        file_content (bytes): Contenu de l'image
        file_path (str): Chemin du fichier image

    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """

    try:
        # Ouvrir l'image directement avec PIL
        image = Image.open(io.BytesIO(file_content))

        # Extraire le texte avec tesseract
        text_ocr = tesserocr.image_to_text(image, lang="fra")

        # Nettoyer le texte
        text_ocr = text_ocr.strip()

        # Vérifier que du texte a été extrait
        if not text_ocr:
            print(f"Attention: Aucun texte détecté dans l'image {file_path}")
            return "", True  # OCR utilisé mais pas de texte trouvé

        return text_ocr, True  # OCR utilisé avec succès

    except Exception as e:
        print(f"Erreur lors de l'extraction du texte de l'image {file_path}: {e}")
        return "", False


def find_libreoffice_executable():
    result = subprocess.run(["which", "libreoffice"], capture_output=True, text=True)
    if result.returncode == 0:
        return "libreoffice"
    else:
        # Essayer d'autres chemins possibles
        possible_paths = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # macOS
            "/usr/bin/libreoffice",  # Linux
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe",  # Windows
            "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",  # Windows 32-bit
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

    return None


def extract_text_from_doc_libreoffice(file_content: bytes, file_path: str):
    """
    Extrait le texte d'un fichier .doc en utilisant LibreOffice (avec gestion d'erreurs robuste)
    """

    libreoffice_path = find_libreoffice_executable()
    if not libreoffice_path:
        logger.warning("LibreOffice n'est pas installé ou pas trouvé dans le PATH")
        return "", False

    with tempfile.TemporaryDirectory() as tmpdirname:
        local_file_path = os.path.join(tmpdirname, "file.doc")
        with open(local_file_path, "wb") as f:
            f.write(file_content)

        cmd = [
            libreoffice_path,
            "--headless",
            "--convert-to",
            "txt",
            "--outdir",
            tmpdirname,
            local_file_path,
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            logger.exception("Error libreoffice (timeout)\n%s", result.stdout)

        if result.returncode != 0:
            logger.error("Error libreoffice (unknown):\n%s", result.stdout)
            return "", False
        else:
            output_path = os.path.join(tmpdirname, "file.txt")
            try:
                with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                return text.strip(), False
            except FileNotFoundError:
                logger.error("Error libreoffice (output file not found)\n%s", result.stdout)
                return "", False


def extract_text_from_doc_docx2txt(file_content: bytes, file_path: str):
    """
    Essaie d'extraire le texte d'un fichier .doc avec docx2txt (parfois ça marche)
    """

    try:
        # Essayer docx2txt sur le fichier .doc (parfois ça fonctionne)
        text = docx2txt.process(io.BytesIO(file_content))

        if text and len(text.strip()) > 10:
            return text.strip(), False
        else:
            return "", False

    except Exception as e:
        print(f"docx2txt ne peut pas traiter {file_path}: {e}")
        return "", False


def is_text_readable(text):
    """
    Vérifie si le texte extrait est lisible (pas du binaire mal décodé)
    """
    if not text or len(text.strip()) < 10:
        return False

    # Compter les caractères imprimables vs non-imprimables
    printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
    total_chars = len(text)

    # Si moins de 70% de caractères imprimables, c'est probablement du binaire mal décodé
    if total_chars > 0 and (printable_chars / total_chars) < 0.7:
        return False

    # Vérifier s'il y a trop de caractères spéciaux bizarres
    # Caractères français et européens acceptables
    acceptable_chars = set("àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß")
    weird_chars = sum(1 for c in text if ord(c) > 127 and c not in acceptable_chars)
    if total_chars > 0 and (weird_chars / total_chars) > 0.3:
        return False

    # Vérifier la présence de mots français/anglais communs
    words = text.split()
    if len(words) > 5:
        # Mots français et anglais communs
        common_words = {
            "le",
            "la",
            "les",
            "de",
            "du",
            "des",
            "et",
            "ou",
            "à",
            "au",
            "aux",
            "dans",
            "sur",
            "par",
            "pour",
            "avec",
            "sans",
            "sous",
            "entre",
            "vers",
            "chez",
            "depuis",
            "jusqu",
            "pendant",
            "après",
            "avant",
            "the",
            "and",
            "or",
            "of",
            "to",
            "in",
            "on",
            "at",
            "by",
            "for",
            "with",
            "without",
            "from",
            "into",
            "document",
            "fichier",
            "texte",
            "page",
            "section",
            "paragraphe",
            "table",
            "image",
            "figure",
            "marché",
            "public",
            "contrat",
            "projet",
            "travaux",
            "prestation",
            "service",
            "produit",
        }

        # Compter les mots communs trouvés
        common_word_count = sum(1 for word in words if word.lower().strip(".,;:!?()[]{}\"'") in common_words)

        # Si au moins 10% des mots sont des mots communs, c'est probablement du texte lisible
        if len(words) > 0 and (common_word_count / len(words)) >= 0.1:
            return True

    # Vérifier la présence de patterns de texte typiques
    text_patterns = [
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+",  # Noms propres
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",  # Dates
        r"\b\d+[.,]\d+",  # Nombres décimaux
        r"\b[A-Z]{2,}\b",  # Acronymes
        # Mois français
        r"\b(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b",
        # Mois anglais
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
    ]

    pattern_matches = sum(1 for pattern in text_patterns if re.search(pattern, text, re.IGNORECASE))

    # Si au moins 2 patterns sont trouvés, c'est probablement du texte lisible
    if pattern_matches >= 2:
        return True

    # Si aucune des vérifications précédentes n'a réussi, utiliser le critère de base
    return True


def extract_text_from_doc_alternative(file_content: bytes):
    """
    Méthode alternative pour les fichiers .doc problématiques
    Utilise une approche de récupération de texte ASCII de qualité
    """

    try:
        # Chercher uniquement des chaînes de texte ASCII de qualité
        # Pattern pour les mots de 4+ caractères avec lettres et espaces
        ascii_patterns = re.findall(rb"[a-zA-Z\x20-\x7E]{4,}", file_content)

        if ascii_patterns:
            # Essayer de décoder avec différents encodages
            for encoding in ["ascii", "latin-1", "cp1252", "windows-1252"]:
                try:
                    ascii_text = b" ".join(ascii_patterns).decode(encoding, errors="ignore")
                    # Nettoyer les caractères de contrôle
                    ascii_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", " ", ascii_text)
                    ascii_text = re.sub(r"\s+", " ", ascii_text).strip()

                    words = ascii_text.split()
                    if len(words) > 10:
                        # Vérifier que c'est du texte lisible (pas du binaire)
                        readable_words = sum(1 for word in words if len(word) > 2 and word.isalpha())
                        if readable_words > len(words) * 0.6:  # Au moins 60% de mots lisibles
                            # Validation finale de la qualité
                            printable_chars = sum(1 for c in ascii_text if c.isprintable() or c.isspace())
                            total_chars = len(ascii_text)

                            if (
                                total_chars > 0 and (printable_chars / total_chars) > 0.9
                            ):  # 90% de caractères imprimables
                                return ascii_text, False
                except UnicodeDecodeError:
                    continue

        # Si la méthode ASCII échoue, essayer une extraction plus basique
        # Chercher des blocs de texte séparés par des caractères de contrôle
        text_blocks = re.split(rb"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]+", file_content)

        for block in text_blocks:
            if len(block) > 30:  # Blocs significatifs
                for encoding in ["ascii", "latin-1", "cp1252"]:
                    try:
                        decoded = block.decode(encoding, errors="ignore")
                        # Nettoyer et garder seulement les caractères imprimables
                        cleaned = re.sub(r"[^\x20-\x7E]", " ", decoded)
                        cleaned = re.sub(r"\s+", " ", cleaned).strip()

                        words = cleaned.split()
                        if len(words) > 5:
                            # Vérifier la qualité du texte
                            readable_words = sum(1 for word in words if len(word) > 2 and word.isalpha())

                            if readable_words > len(words) * 0.5:  # Au moins 50% de mots lisibles
                                # Validation finale
                                printable_chars = sum(1 for c in cleaned if c.isprintable() or c.isspace())
                                total_chars = len(cleaned)

                                if total_chars > 0 and (printable_chars / total_chars) > 0.9:
                                    return cleaned, False
                                break
                    except UnicodeDecodeError:
                        continue

        return "", False

    except Exception as e:
        print(f"Erreur lors de l'extraction alternative: {e}")
        return "", False


def extract_text_from_doc_ole2(file_content: bytes):
    """
    Méthode d'extraction utilisant l'analyse OLE2 pour les fichiers .doc
    """

    try:
        # Essayer d'utiliser python-docx2txt ou une bibliothèque similaire
        # Cette méthode est plus spécialisée pour les fichiers .doc OLE2

        # Patterns spécifiques aux fichiers Word OLE2
        word_patterns = [
            rb"WordDocument",  # Signature Word
            rb"FIB",  # File Information Block
            rb"Table",  # Tables Word
            rb"1Table",  # Table 1
            rb"0Table",  # Table 0
        ]

        # Vérifier que c'est bien un fichier Word OLE2
        is_word_doc = any(pattern in file_content for pattern in word_patterns)
        if not is_word_doc:
            return "", False

        # Extraire le texte en cherchant des patterns de texte dans le format OLE2
        # Chercher des chaînes de texte Unicode (UTF-16 LE)
        unicode_patterns = re.findall(rb"[\x20-\x7E\x00]{2,}", file_content)

        extracted_texts = []
        for pattern in unicode_patterns:
            try:
                # Essayer de décoder comme UTF-16 LE
                decoded = pattern.decode("utf-16le", errors="ignore")
                # Nettoyer le texte
                cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", " ", decoded)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()

                if len(cleaned) > 5 and cleaned.isprintable():
                    extracted_texts.append(cleaned)
            except UnicodeDecodeError:
                continue

        if extracted_texts:
            # Combiner tous les textes extraits
            combined_text = " ".join(extracted_texts)
            # Nettoyer et dédupliquer
            combined_text = re.sub(r"\s+", " ", combined_text).strip()

            if len(combined_text) > 50:
                return combined_text, False

        return "", False

    except Exception as e:
        print(f"Erreur lors de l'extraction OLE2: {e}")
        return "", False


def extract_text_from_doc(file_content: bytes, file_path: str):
    """
    Extrait le texte d'un fichier .doc avec plusieurs méthodes de fallback
    Gère les erreurs de déploiement LibreOffice
    """

    print(f"  - Extraction du texte de {file_path} ({len(file_content)} octets)")

    # Méthode 1: LibreOffice avec gestion d'erreurs robuste
    print("    - Tentative 1: LibreOffice (conversion directe)")
    text, is_ocr = extract_text_from_doc_libreoffice(file_content, file_path)
    if text and is_text_readable(text):
        print(f"    - Succès avec LibreOffice: {len(text)} caractères, {len(text.split())} mots")
        return text, is_ocr

    # Méthode 2: Essayer docx2txt (parfois ça marche sur les .doc)
    print("    - Tentative 2: docx2txt direct")
    text, is_ocr = extract_text_from_doc_docx2txt(file_content, file_path)
    if text and is_text_readable(text):
        print(f"    - Succès avec docx2txt: {len(text)} caractères, {len(text.split())} mots")
        return text, is_ocr

    # Méthode 3: Extraction OLE2 spécialisée
    print("    - Tentative 3: Extraction OLE2 spécialisée")
    text, is_ocr = extract_text_from_doc_ole2(file_content)
    if text and is_text_readable(text):
        print(f"    - Succès avec extraction OLE2: {len(text)} caractères, {len(text.split())} mots")
        return text, is_ocr

    # Méthode 4: Extraction alternative pour fichiers problématiques
    print("    - Tentative 4: Extraction alternative (ASCII)")
    text, is_ocr = extract_text_from_doc_alternative(file_content)
    if text and is_text_readable(text):
        print(f"    - Succès avec extraction alternative: {len(text)} caractères, {len(text.split())} mots")
        return text, is_ocr

    # Si toutes les méthodes échouent
    print(f"  - Échec: Impossible d'extraire le texte de {file_path}")
    print("  - Le fichier peut être corrompu ou dans un format non supporté")
    return "", False


def extract_text(file_content: bytes, file_path: str, file_type: str, word_threshold=50):
    """
    Extrait le texte d'un fichier selon son type.

    Args:
        filename (str): Nom du fichier
        file_path (str): Chemin du fichier
        file_type (str): Type du fichier (pdf, docx, doc, odt)
        word_threshold (int): Seuil de mots pour décider d'utiliser l'OCR (PDF uniquement)

    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """

    if not file_content:
        return "", False

    if file_type == "unknown":
        logger.warning(f"Unknown file type for {file_path} (type={file_type!r})")
        return "", False
    elif file_type == "pdf":
        text, is_ocr = extract_text_from_pdf(file_content, word_threshold)
    elif file_type == "docx":
        text, is_ocr = extract_text_from_docx(file_content, file_path)
    elif file_type == "odt":
        text, is_ocr = extract_text_from_odt(file_content, file_path)
    elif file_type == "txt":
        text, is_ocr = extract_text_from_txt(file_content, file_path)
    elif file_type in ["png", "jpg", "jpeg", "tiff", "tif"]:
        text, is_ocr = extract_text_from_image(file_content, file_path)
    elif file_type == "doc":
        text, is_ocr = extract_text_from_doc(file_content, file_path)
    else:
        raise ValueError(f"Invalid file type for {file_path} (type={file_type!r})")

    text = clean_nul_bytes(text)

    return text, is_ocr


def df_extract_text(
    dfFiles: pd.DataFrame, word_threshold=50, save_path=None, directory_path=None, save_grist=False, max_workers=4
):
    """
    Traite le dataframe complet:
    1. Ajoute les colonnes text, is_OCR, nb_mot dans un nouveau DataFrame
    2. Lance le traitement : extrait le texte en appelant extract_text
    3. Indique si l'OCR a été utilisé
    4. Calcule les stratistiques sur les PDFs et l'OCR

    Args:
        df (DataFrame): DataFrame avec une colonne 'filename', 'path', 'extension'
        word_threshold (int): Seuil de mots pour décider d'utiliser l'OCR

    Returns:
        DataFrame: DataFrame traité avec les colonnes additionnelles
    """
    dfResult = dfFiles.copy(deep=False)

    # Initialiser les colonnes avec des valeurs par défaut
    dfResult["text"] = ""
    dfResult["is_OCR"] = False
    dfResult["nb_mot"] = 0

    # Traiter chaque fichier avec une barre de progression
    print(f"\nTraitement de {len(dfResult)} fichiers PDF...")

    # Traitement parallèle
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_df_row, row, word_threshold) for row in dfResult.reset_index().to_dict("records")
        ]

        results = []
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Extraction du texte des fichiers (parallèle)"
        ):
            results.append(future.result())
            idx, result = future.result()

            for key, value in result.items():
                dfResult.at[idx, key] = value

    # Afficher les statistiques finales
    display_pdf_stats(dfResult, "Statistiques finales après extraction de texte")
    try:
        if save_grist:
            update_records_in_grist(
                dfResult,
                key_column="filename",
                table_url=URL_TABLE_ATTACHMENTS,
                api_key=API_KEY_GRIST,
                columns_to_update=["text", "is_OCR", "nb_mot"],
                batch_size=30,
            )

        if save_path:
            full_save_path = f"{save_path}/textsExtraits_{directory_path.split('/')[-1]}_{getDate()}.csv"
            dfResult.to_csv(full_save_path, index=False)
            print(f"Liste des fichiers sauvegardées dans {full_save_path}")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde du DataFrame : {e}")

    # Retourner le DataFrame traité
    return dfResult


def process_df_row(row, word_threshold):
    """
    Fonction pour traiter une ligne du DataFrame.
    Extrait le texte du PDF et met à jour les colonnes correspondantes.
    """

    filename = row["filename"]
    folder = row["dossier"]
    extension = row["extension"]

    file_path = f"{folder}/{filename}"

    try:
        text, is_ocr, nb_words = process_file(file_path, extension, word_threshold)
    except FileNotFoundError:
        logger.error("Erreur: Le fichier %s n'existe pas", file_path)
        text, is_ocr = "", False
        nb_words = 0
    except Exception as e:
        logger.exception("Erreur lors de l'extraction du texte du fichier %s : %s", file_path, e)

    return row["index"], {"text": text, "is_OCR": is_ocr, "nb_mot": nb_words}


def process_file(file_path: str, extension: str, word_threshold: int = 50):
    """
    Process a single file to extract text content with OCR support if needed.

    Args:
        file_path: Path to the file to process
        extension: File extension indicating type (pdf, docx, etc)
        word_threshold: Minimum word count threshold below which OCR is triggered for PDFs

    Returns:
        tuple:
            - extracted text (str)
            - whether OCR was used (bool)
            - word count (int)

    Raises:
        UnsupportedFileType: If file extension is not supported
        FileNotFoundError: If file does not exist
    """

    if extension not in SUPPORTED_FILES_TYPE:
        raise UnsupportedFileType(f"Unsupported filed type {extension!r}")

    with default_storage.open(file_path, "rb") as f:
        file_content = f.read()

    with log_execution_time(f"extract_text({file_path})"):
        text, is_ocr = extract_text(file_content, file_path, extension, word_threshold)

    nb_words = count_words(text)
    return text, is_ocr, nb_words


def save_df_extract_text_result(df: pd.DataFrame):
    # Clean NUL bytes from text columns before saving to PostgreSQL
    from app.utils import clean_nul_bytes_from_dataframe

    df_clean = clean_nul_bytes_from_dataframe(df, ["text"])
    bulk_update_attachments(df_clean, ["is_OCR", "nb_mot", "text"])
