import re
from difflib import SequenceMatcher
from pathlib import Path

from docia.file_processing.processor.text_extraction.text_extraction import clean_nul_bytes

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "documents"


def normalize_text_for_token(text):
    # Remove extra whitespace, lowercase, strip
    text = re.sub(r"\s+", " ", text.strip())
    return text.lower()


def similarity_ratio(str1, str2):
    tokens1 = normalize_text_for_token(str1).split()
    tokens2 = normalize_text_for_token(str2).split()

    return SequenceMatcher(None, tokens1, tokens2).ratio()


def assert_similar_text(extracted, threshold):
    with open(ASSETS_DIR / "lettre.md", "r") as f:
        expected = f.read()

    similarity = similarity_ratio(extracted, expected)
    assert similarity > threshold, f"Similarity {similarity:.2%} below threshold"


def test_clean_nul_bytes():
    text = "\x00Hello \x00World!\x00"
    cleaned = clean_nul_bytes(text)
    assert cleaned == "Hello World!"
