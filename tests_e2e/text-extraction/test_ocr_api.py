import os
import sys
from pathlib import Path

import django

sys.path.append(".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
django.setup()

from docia.file_processing.llm.client import LLMClient  # noqa: E402

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LETTRE_OCR_PATH = ASSETS_DIR / "lettre-ocr.pdf"

# Phrases clés (contenu attendu de lettre.md) de la lettre de mission qui doivent être reconnues par l'OCR
PHRASES_ATTENDUES = [
    "lettre de mission",
    "paris",
    "mission de conseil",
    "technova solutions",
    "euros",
    "jean dupont",
    "sophie martin",
    "cabinet conseil",
    "transformation digitale",
    "novembre 2025",
    "avril 2026",
]


def test_ocr_api_extracts_text_from_lettre_ocr():
    """L'API OCR doit extraire du texte de bonne qualité du document lettre-ocr.pdf."""
    pdf_content = LETTRE_OCR_PATH.read_bytes()
    client = LLMClient()
    text = client.ocr_pdf(pdf_content)

    assert text, "L'OCR doit renvoyer du texte non vide"
    assert len(text.strip()) >= 100, "Le texte extrait doit contenir au moins 100 caractères"

    # Normalisation pour comparaison (minuscules, espaces multiples réduits)
    text_norm = " ".join(text.lower().split())

    # Vérification des phrases clés de la lettre de mission
    for phrase in PHRASES_ATTENDUES:
        assert phrase in text_norm, f"Phrase attendue non trouvée dans l'OCR : {phrase!r}"

    # Montant : 85 000 euros (OCR peut renvoyer "85 000" ou "85000")
    assert ("85 000" in text_norm or "85000" in text_norm) and "euros" in text_norm, (
        "Le montant (85 000 euros HT) doit être présent dans le texte OCR"
    )
