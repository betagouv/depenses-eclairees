import re
from difflib import SequenceMatcher
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "documents"


def normalize_text(text):
    # Remove extra whitespace, lowercase, strip
    text = re.sub(r"\s+", " ", text.strip())
    return text.lower()


def similarity_ratio(str1, str2):
    tokens1 = normalize_text(str1).split()
    tokens2 = normalize_text(str2).split()

    return SequenceMatcher(None, tokens1, tokens2).ratio()


def assert_similar_text(extracted, threshold):
    with open(ASSETS_DIR / "lettre.md", "r") as f:
        expected = f.read()

    similarity = similarity_ratio(extracted, expected)
    assert similarity > threshold, f"Similarity {similarity:.2%} below threshold"
