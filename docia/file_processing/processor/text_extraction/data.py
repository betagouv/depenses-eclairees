from dataclasses import dataclass


@dataclass
class TextExtractionResult:
    text: str
    is_ocr: bool
    nb_words: int
    nb_pages: int | None
    nb_tokens: int
