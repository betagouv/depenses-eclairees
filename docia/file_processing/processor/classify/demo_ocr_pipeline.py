"""Pipeline démo prod : OCR mistral (document entier) + openweight-medium."""

from __future__ import annotations

import time
from dataclasses import dataclass

import pymupdf

from docia.file_processing.processor.classify.demo_llm import DemoLlmResult, classify_with_llm_demo, ensure_django_ready


@dataclass(frozen=True, slots=True)
class DemoOcrPipelineResult:
    ocr_ms: float
    classify_ms: float
    total_ms: float
    wall_ms: float
    raw_text: str
    nb_pages: int
    pages_extracted: int
    nb_mot: int
    ocr_model: str
    llm: DemoLlmResult
    ocr_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.ocr_error is None and self.llm.ok


def _pdf_page_count(file_content: bytes) -> int:
    doc = pymupdf.open(stream=file_content, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()


def mistral_ocr_full_pdf(file_content: bytes) -> tuple[str, int, float, str | None]:
    """Même logique que prod : mistral-ocr, document entier (chunk si gros PDF)."""
    ensure_django_ready()
    from docia.file_processing.processor.text_extraction.text_extract_document import extract_text_from_pdf

    t0 = time.perf_counter()
    try:
        text, _, nb_pages = extract_text_from_pdf(file_content, ocr_tool="mistral-ocr")
        ocr_ms = (time.perf_counter() - t0) * 1000.0
        return (text or "").strip(), nb_pages, ocr_ms, None
    except Exception as exc:
        ocr_ms = (time.perf_counter() - t0) * 1000.0
        return "", _pdf_page_count(file_content), ocr_ms, str(exc)


_mistral_ocr_prod_pdf = mistral_ocr_full_pdf


def run_ocr_llm_pipeline(file_content: bytes, filename: str) -> DemoOcrPipelineResult:
    """Pipeline prod : mistral-ocr-2512 sur tout le PDF, puis openweight-medium."""
    ensure_django_ready()
    from docia.file_processing.processor.constants import DEFAULT_CLASSIFICATION_MODEL, DEFAULT_OCR_MODEL

    t_wall = time.perf_counter()
    text, nb_pages, ocr_ms, ocr_error = mistral_ocr_full_pdf(file_content)

    if ocr_error:
        wall_ms = (time.perf_counter() - t_wall) * 1000.0
        return DemoOcrPipelineResult(
            ocr_ms=ocr_ms,
            classify_ms=0.0,
            total_ms=ocr_ms,
            wall_ms=wall_ms,
            raw_text="",
            nb_pages=nb_pages,
            pages_extracted=nb_pages,
            nb_mot=0,
            ocr_model=DEFAULT_OCR_MODEL,
            llm=DemoLlmResult(
                label="",
                coarse=None,
                model=DEFAULT_CLASSIFICATION_MODEL,
                duration_ms=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                error="OCR en échec",
            ),
            ocr_error=ocr_error,
        )

    from docia.file_processing.processor.classify.demo_infer import count_words

    llm = classify_with_llm_demo(filename, text, llm_model=DEFAULT_CLASSIFICATION_MODEL)
    classify_ms = llm.duration_ms
    total_ms = ocr_ms + classify_ms
    wall_ms = (time.perf_counter() - t_wall) * 1000.0
    return DemoOcrPipelineResult(
        ocr_ms=ocr_ms,
        classify_ms=classify_ms,
        total_ms=total_ms,
        wall_ms=wall_ms,
        raw_text=text,
        nb_pages=nb_pages,
        pages_extracted=nb_pages,
        nb_mot=count_words(text),
        ocr_model=DEFAULT_OCR_MODEL,
        llm=llm,
        ocr_error=None,
    )