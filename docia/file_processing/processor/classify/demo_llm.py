"""Classification LLM pour la démo Streamlit (Django + API prod)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from docia.file_processing.processor.classify.label_hierarchy import map_llm_to_coarse


def ensure_django_ready() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docia.settings")
    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


@dataclass(frozen=True, slots=True)
class DemoLlmResult:
    label: str
    coarse: str | None
    model: str
    duration_ms: float
    prompt_tokens: int
    completion_tokens: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def classify_with_llm_demo(filename: str, raw_text: str, *, llm_model: str | None = None) -> DemoLlmResult:
    """Appel LLM prod (même prompt que classify_file_with_llm)."""
    ensure_django_ready()
    from docia.file_processing.processor.classifier import DIC_CLASS_FILE_BY_NAME, classify_file_with_llm
    from docia.file_processing.processor.constants import DEFAULT_CLASSIFICATION_MODEL

    model = llm_model or DEFAULT_CLASSIFICATION_MODEL
    t0 = time.perf_counter()
    try:
        outcome = classify_file_with_llm(
            filename,
            raw_text,
            DIC_CLASS_FILE_BY_NAME,
            llm_model=model,
        )
        label = outcome.classification
        coarse = map_llm_to_coarse(label)
        usage = outcome.usage
        return DemoLlmResult(
            label=label,
            coarse=coarse,
            model=outcome.model,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
    except Exception as exc:
        return DemoLlmResult(
            label="",
            coarse=None,
            model=model,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            prompt_tokens=0,
            completion_tokens=0,
            error=str(exc),
        )