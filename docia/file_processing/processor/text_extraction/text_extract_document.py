"""
Extraction de texte depuis les documents : PDF, images, doc, docx, odt, txt.
"""

import io
import logging
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import docx2txt
import pymupdf
import tesserocr
from PIL import Image

from app.utils import count_words
from docia.file_processing.llm.client import LLMClient
from docia.file_processing.processor.pdf_drawings import add_drawings_to_pdf

logger = logging.getLogger("docia." + __name__)


def extract_text_from_pdf(file_content: bytes, word_threshold=50, ocr_tool: str = "mistral-ocr"):
    """
    Extrait le texte d'un PDF. Si le PDF contient moins de mots que le seuil défini,
    utilise l'OCR pour extraire le texte.

    Args:
        file_content (bytes): Contenu du fichier
        word_threshold (int): Nombre minimal de mots en dessous duquel l'OCR est utilisé
        ocr_tool (str): "mistral-ocr" (défaut) pour l'API Albert/OpenGateLLM, "tesseract" pour OCR local Tesseract

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

    # Si peu de mots sont extraits, c'est peut-être une image scannée → OCR
    else:
        is_ocr_used = True
        if ocr_tool == "tesseract":
            # OCR local : PDF → pixmap (pymupdf) → image → tesserocr
            parts = []
            for i in range(len(doc)):
                pix = doc.load_page(i).get_pixmap(matrix=pymupdf.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                parts.append(tesserocr.image_to_text(img, lang="fra").strip())
            text = "\n\n".join(parts).strip()
        else:
            llm_client = LLMClient()
            text = llm_client.ocr_pdf(file_content)

    return text, is_ocr_used


def extract_text_from_docx(file_content: bytes, file_path: str):
    """
    Extrait le texte d'un fichier DOCX avec gestion d'erreurs robuste.
    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """
    try:
        text = docx2txt.process(io.BytesIO(file_content))
        if text is None:
            print(f"Attention: Aucun texte extrait de {file_path}")
            return "", False
        text = text.strip()
        if not text:
            print(f"Attention: Le fichier {file_path} ne contient pas de texte lisible")
            return "", False
        return text, False
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"Erreur: {e}")
        return "", False
    except Exception as e:
        print(f"Erreur inattendue lors de l'extraction du texte de {file_path}: {e}")
        return "", False


def extract_text_from_odt(file_content: bytes, file_path: str):
    """
    Extrait le texte d'un fichier ODT avec gestion d'erreurs robuste.
    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """
    try:
        with zipfile.ZipFile(io.BytesIO(file_content), "r") as zip_file:
            if "content.xml" not in zip_file.namelist():
                return "", False
            content = zip_file.read("content.xml")
            root = ET.fromstring(content)
            text_parts = []
            for elem in root.iter():
                if elem.text:
                    text_parts.append(elem.text.strip())
            text = "\n".join([part for part in text_parts if part])
            if text and text.strip():
                return text.strip(), False
        return "", False
    except Exception as e:
        print(f"Erreur lors de l'extraction du texte de {file_path}: {e}")
        return "", False


def extract_text_from_txt(file_content: bytes, file_path: str):
    """Extrait le texte d'un fichier TXT."""
    try:
        return file_content.decode("utf-8", errors="ignore"), False
    except Exception as e:
        print(f"Erreur inattendue lors de l'extraction du texte de {file_path}: {e}")
        return "", False


def extract_text_from_image(file_content: bytes, file_path: str):
    """
    Extrait le texte d'une image (PNG, JPG, JPEG, TIFF) avec OCR.
    Returns:
        tuple: (texte extrait, booléen indiquant si l'OCR a été utilisé)
    """
    try:
        image = Image.open(io.BytesIO(file_content))
        text_ocr = tesserocr.image_to_text(image, lang="fra").strip()
        if not text_ocr:
            print(f"Attention: Aucun texte détecté dans l'image {file_path}")
            return "", True
        return text_ocr, True
    except Exception as e:
        print(f"Erreur lors de l'extraction du texte de l'image {file_path}: {e}")
        return "", False


def find_libreoffice_executable():
    result = subprocess.run(["which", "libreoffice"], capture_output=True, text=True)
    if result.returncode == 0:
        return "libreoffice"
    possible_paths = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/libreoffice",
        "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
        "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def extract_text_from_doc_libreoffice(file_content: bytes, file_path: str):
    """Extrait le texte d'un fichier .doc en utilisant LibreOffice."""
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
            logger.exception("Error libreoffice (timeout)")
            return "", False

        if result.returncode != 0:
            logger.error("Error libreoffice (unknown):\n%s", result.stdout)
            return "", False
        output_path = os.path.join(tmpdirname, "file.txt")
        try:
            with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip(), False
        except FileNotFoundError:
            logger.error("Error libreoffice (output file not found)\n%s", result.stdout)
            return "", False


def extract_text_from_doc_docx2txt(file_content: bytes, file_path: str):
    """Essaie d'extraire le texte d'un fichier .doc avec docx2txt."""
    try:
        text = docx2txt.process(io.BytesIO(file_content))
        if text and len(text.strip()) > 10:
            return text.strip(), False
        return "", False
    except Exception as e:
        print(f"docx2txt ne peut pas traiter {file_path}: {e}")
        return "", False


def is_text_readable(text):
    """Vérifie si le texte extrait est lisible (pas du binaire mal décodé)."""
    if not text or len(text.strip()) < 10:
        return False

    printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
    total_chars = len(text)
    if total_chars > 0 and (printable_chars / total_chars) < 0.7:
        return False

    acceptable_chars = set("àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß")
    weird_chars = sum(1 for c in text if ord(c) > 127 and c not in acceptable_chars)
    if total_chars > 0 and (weird_chars / total_chars) > 0.3:
        return False

    words = text.split()
    if len(words) > 5:
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
        common_word_count = sum(1 for word in words if word.lower().strip(".,;:!?()[]{}\"'") in common_words)
        if len(words) > 0 and (common_word_count / len(words)) >= 0.1:
            return True

    text_patterns = [
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
        r"\b\d+[.,]\d+",
        r"\b[A-Z]{2,}\b",
        r"\b(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b",
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
    ]
    pattern_matches = sum(1 for pattern in text_patterns if re.search(pattern, text, re.IGNORECASE))
    if pattern_matches >= 2:
        return True

    return True


def extract_text_from_doc_alternative(file_content: bytes):
    """Méthode alternative pour les fichiers .doc problématiques (extraction ASCII)."""
    try:
        ascii_patterns = re.findall(rb"[a-zA-Z\x20-\x7E]{4,}", file_content)
        if ascii_patterns:
            for encoding in ["ascii", "latin-1", "cp1252", "windows-1252"]:
                try:
                    ascii_text = b" ".join(ascii_patterns).decode(encoding, errors="ignore")
                    ascii_text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", " ", ascii_text)
                    ascii_text = re.sub(r"\s+", " ", ascii_text).strip()
                    words = ascii_text.split()
                    if len(words) > 10:
                        readable_words = sum(1 for word in words if len(word) > 2 and word.isalpha())
                        if readable_words > len(words) * 0.6:
                            printable_chars = sum(1 for c in ascii_text if c.isprintable() or c.isspace())
                            total_chars = len(ascii_text)
                            if total_chars > 0 and (printable_chars / total_chars) > 0.9:
                                return ascii_text, False
                except UnicodeDecodeError:
                    continue

        text_blocks = re.split(rb"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]+", file_content)
        for block in text_blocks:
            if len(block) > 30:
                for encoding in ["ascii", "latin-1", "cp1252"]:
                    try:
                        decoded = block.decode(encoding, errors="ignore")
                        cleaned = re.sub(r"[^\x20-\x7E]", " ", decoded)
                        cleaned = re.sub(r"\s+", " ", cleaned).strip()
                        words = cleaned.split()
                        if len(words) > 5:
                            readable_words = sum(1 for word in words if len(word) > 2 and word.isalpha())
                            if readable_words > len(words) * 0.5:
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
    """Extraction OLE2 pour les fichiers .doc."""
    try:
        word_patterns = [rb"WordDocument", rb"FIB", rb"Table", rb"1Table", rb"0Table"]
        if not any(pattern in file_content for pattern in word_patterns):
            return "", False

        unicode_patterns = re.findall(rb"[\x20-\x7E\x00]{2,}", file_content)
        extracted_texts = []
        for pattern in unicode_patterns:
            try:
                decoded = pattern.decode("utf-16le", errors="ignore")
                cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", " ", decoded)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                if len(cleaned) > 5 and cleaned.isprintable():
                    extracted_texts.append(cleaned)
            except UnicodeDecodeError:
                continue

        if extracted_texts:
            combined_text = " ".join(extracted_texts)
            combined_text = re.sub(r"\s+", " ", combined_text).strip()
            if len(combined_text) > 50:
                return combined_text, False
        return "", False
    except Exception as e:
        print(f"Erreur lors de l'extraction OLE2: {e}")
        return "", False


def extract_text_from_doc(file_content: bytes, file_path: str):
    """Extrait le texte d'un fichier .doc avec plusieurs méthodes de fallback."""
    print(f"  - Extraction du texte de {file_path} ({len(file_content)} octets)")

    text, is_ocr = extract_text_from_doc_libreoffice(file_content, file_path)
    if text and is_text_readable(text):
        return text, is_ocr

    text, is_ocr = extract_text_from_doc_docx2txt(file_content, file_path)
    if text and is_text_readable(text):
        return text, is_ocr

    text, is_ocr = extract_text_from_doc_ole2(file_content)
    if text and is_text_readable(text):
        return text, is_ocr

    text, is_ocr = extract_text_from_doc_alternative(file_content)
    if text and is_text_readable(text):
        return text, is_ocr

    print(f"  - Échec: Impossible d'extraire le texte de {file_path}")
    return "", False
