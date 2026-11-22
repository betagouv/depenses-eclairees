"""OCR PyMuPDF4LLM pour la démo pipeline 1 (Tesseract / hybride, sans RapidOCR)."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import pymupdf
import pymupdf4llm

logger = logging.getLogger(__name__)


def _fast_ocr_attempts() -> list[tuple[Callable[..., Any] | None, str]]:
    attempts: list[tuple[Callable[..., Any] | None, str]] = []
    try:
        from pymupdf4llm.ocr import tesseract_api

        attempts.append((tesseract_api.exec_ocr, "tesseract (hybride)"))
    except ImportError:
        pass
    attempts.append((None, "auto PyMuPDF (hybride)"))
    return attempts


def resolve_pymupdf4llm_ocr() -> tuple[Any | None, str]:
    for fn, label in _fast_ocr_attempts():
        if fn is not None:
            return fn, label
    return None, "auto PyMuPDF (hybride)"


def to_markdown_with_demo_ocr(doc, page_indices: list[int]) -> tuple[str, str]:
    if not page_indices:
        return "", "aucune page"

    last_error: Exception | None = None
    for ocr_fn, engine in _fast_ocr_attempts():
        kwargs: dict[str, Any] = {"pages": page_indices}
        if ocr_fn is not None:
            kwargs["ocr_function"] = ocr_fn
        try:
            text = pymupdf4llm.to_markdown(doc, **kwargs)
            return (text or "").strip(), engine
        except Exception as exc:
            logger.warning("OCR plugin %s failed: %s", engine, exc)
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    return "", "échec"


def tesseract_full_pdf_markdown(file_content: bytes) -> tuple[str, int, str, float, str | None]:
    """Tesseract / hybride PyMuPDF4LLM sur **toutes** les pages (équivalent OCR local complet)."""
    t0 = time.perf_counter()
    doc = pymupdf.open(stream=file_content, filetype="pdf")
    try:
        nb_pages = doc.page_count
        indices = list(range(nb_pages))
        text, engine = to_markdown_with_demo_ocr(doc, indices)
        extract_ms = (time.perf_counter() - t0) * 1000.0
        return (text or "").strip(), nb_pages, engine, extract_ms, None
    except Exception as exc:
        extract_ms = (time.perf_counter() - t0) * 1000.0
        return "", doc.page_count, "échec", extract_ms, str(exc)
    finally:
        doc.close()