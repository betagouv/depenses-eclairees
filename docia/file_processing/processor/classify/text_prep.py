import re

from unidecode import unidecode


def normalize_filename(filename: str | None) -> str:
    if not filename:
        return ""
    base = filename.rsplit("/", maxsplit=1)[-1]
    base = unidecode(base.lower())
    base = re.sub(r"[^a-z0-9]+", " ", base)
    return " ".join(base.split())


def prepare_text_head(text: str | None, max_chars: int = 2000) -> str:
    if not text:
        return ""
    cleaned = unidecode(text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars]