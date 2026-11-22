"""Inférence classify V1 pour démo locale (PDF en mémoire, PyMuPDF4LLM, logreg)."""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd
import pymupdf
from docia.file_processing.processor.classify.artifacts import load_pipeline, load_thresholds
from docia.file_processing.processor.classify.label_display import display_name_for_label
from docia.file_processing.processor.classify.constants import (
    CONTENT_ANALYSIS_CLASSIFICATIONS,
    DEFAULT_OUTPUT_DIR,
    PIPELINE1_MISTRAL_OCR_LABELS,
    PIPELINE1_TESSERACT_FULL_OCR_LABELS,
    TEXT_HEAD_CHARS,
)
from docia.file_processing.processor.classify.evaluate import (
    ROUTING_REJECT_LABEL,
    accept_mask,
    apply_reject,
    predict_frame,
)
from docia.file_processing.processor.classify.demo_pymupdf_ocr import to_markdown_with_demo_ocr
from docia.file_processing.processor.classify.text_prep import normalize_filename, prepare_text_head
DEMO_EXTRACT_MAX_PAGES = 3
DEMO_MIN_WORDS = 30
DEMO_RAW_PREVIEW_CHARS = 6000


@dataclass(frozen=True, slots=True)
class PdfExtractResult:
    raw_text: str
    nb_pages: int
    pages_extracted: int
    nb_mot: int
    extract_ms: float
    too_sparse: bool
    ocr_engine: str = "auto"


@dataclass(frozen=True, slots=True)
class TopClassProba:
    label: str
    display_name: str
    probability: float


@dataclass(frozen=True, slots=True)
class DemoClassifyResult:
    filename: str
    filename_normalized: str
    raw_text_preview: str
    text_2000: str
    nb_mot: int
    nb_pages: int
    pages_extracted: int
    top5: tuple[TopClassProba, ...]
    pred_classifier: str
    pred_display: str
    decision: str
    decision_display: str
    routed_to_llm: bool
    accepted: bool
    tau: float
    margin_threshold: float
    max_proba: float
    margin: float
    passes_tau: bool
    passes_margin: bool
    model_n_classes: int
    extract_ms: float
    infer_ms: float
    total_ms: float
    too_sparse: bool
    sparse_warning: str | None = None
    inference_skipped: bool = False
    with_llm: bool = False
    llm_label: str | None = None
    llm_coarse: str | None = None
    llm_display: str | None = None
    llm_coarse_display: str | None = None
    llm_model: str | None = None
    llm_ms: float = 0.0
    llm_error: str | None = None
    llm_prompt_tokens: int | None = None
    llm_completion_tokens: int | None = None
    logreg_llm_same_coarse: bool | None = None
    parallel_infer_ms: float = 0.0
    pipeline1_total_ms: float = 0.0
    with_ocr_pipeline: bool = False
    pipeline2_total_ms: float = 0.0
    pipeline2_ocr_ms: float = 0.0
    pipeline2_classify_ms: float = 0.0
    pipeline2_wall_ms: float = 0.0
    pipelines_wall_ms: float = 0.0
    pipeline2_label: str | None = None
    pipeline2_display: str | None = None
    pipeline2_coarse: str | None = None
    pipeline2_coarse_display: str | None = None
    pipeline2_error: str | None = None
    pipeline2_raw_preview: str | None = None
    pipeline2_nb_mot: int | None = None
    pipeline1_faster: bool | None = None
    pipeline_speed_ratio: float | None = None
    extract_ocr_engine: str = "auto"
    pipeline1_post_logreg_ocr_ms: float = 0.0
    pipeline1_post_logreg_ran: bool = False
    pipeline1_post_logreg_engine: str | None = None
    pipeline1_post_logreg_skip_reason: str | None = None
    pipeline1_post_logreg_nb_mot: int | None = None
    pipeline1_post_logreg_raw_preview: str | None = None
    pipeline1_post_logreg_error: str | None = None


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text or "", flags=re.UNICODE))


def pipeline1_post_logreg_ocr_plan(
    *,
    decision: str,
    accepted: bool,
) -> tuple[str, str | None]:
    """Étape 3 P1 : mistral (AE, ST) ou Tesseract doc entier (autres CONTENT_ANALYSIS)."""
    if not accepted:
        return "none", "logreg rejeté (routage LLM prod) — pas de 2ᵉ extraction sur P1"
    if decision in PIPELINE1_MISTRAL_OCR_LABELS:
        return "mistral-ocr", None
    if decision in PIPELINE1_TESSERACT_FULL_OCR_LABELS:
        return "tesseract", None
    if decision in CONTENT_ANALYSIS_CLASSIFICATIONS:
        return "none", "classe analyse sans branche OCR démo"
    display = display_name_for_label(decision)
    return "none", f"« {display} » (`{decision}`) hors périmètre analyse"


def _skip_post_logreg_fields(reason: str | None) -> dict[str, object]:
    return {
        "pipeline1_post_logreg_ocr_ms": 0.0,
        "pipeline1_post_logreg_ran": False,
        "pipeline1_post_logreg_engine": None,
        "pipeline1_post_logreg_skip_reason": reason,
        "pipeline1_post_logreg_nb_mot": None,
        "pipeline1_post_logreg_raw_preview": None,
        "pipeline1_post_logreg_error": None,
    }


def _conditional_pipeline1_post_logreg_ocr(
    file_content: bytes,
    logreg: _LogregInferOutcome,
) -> dict[str, object]:
    engine, reason = pipeline1_post_logreg_ocr_plan(decision=logreg.decision, accepted=logreg.accepted)
    if engine == "none":
        return _skip_post_logreg_fields(reason)

    if engine == "mistral-ocr":
        from docia.file_processing.processor.classify.demo_ocr_pipeline import mistral_ocr_full_pdf

        text, _nb_pages, ocr_ms, err = mistral_ocr_full_pdf(file_content)
        engine_label = "mistral-ocr"
    else:
        from docia.file_processing.processor.classify.demo_pymupdf_ocr import tesseract_full_pdf_markdown

        text, _nb_pages, tess_engine, ocr_ms, err = tesseract_full_pdf_markdown(file_content)
        engine_label = f"tesseract ({tess_engine})"

    preview = text[:DEMO_RAW_PREVIEW_CHARS] if text else None
    return {
        "pipeline1_post_logreg_ocr_ms": ocr_ms,
        "pipeline1_post_logreg_ran": err is None,
        "pipeline1_post_logreg_engine": engine_label,
        "pipeline1_post_logreg_skip_reason": None,
        "pipeline1_post_logreg_nb_mot": count_words(text) if text else 0,
        "pipeline1_post_logreg_raw_preview": preview,
        "pipeline1_post_logreg_error": err,
    }


def extract_pdf_text_pymupdf4llm(
    file_content: bytes,
    *,
    max_pages: int = DEMO_EXTRACT_MAX_PAGES,
) -> PdfExtractResult:
    t0 = time.perf_counter()
    doc = pymupdf.open(stream=file_content, filetype="pdf")
    try:
        nb_pages = doc.page_count
        n_extract = min(max_pages, nb_pages)
        page_indices = list(range(n_extract))
        raw_text, ocr_engine = to_markdown_with_demo_ocr(doc, page_indices)
    finally:
        doc.close()
    extract_ms = (time.perf_counter() - t0) * 1000.0
    raw_text = (raw_text or "").strip()
    nb_mot = count_words(raw_text)
    too_sparse = nb_mot < DEMO_MIN_WORDS
    return PdfExtractResult(
        raw_text=raw_text,
        nb_pages=nb_pages,
        pages_extracted=n_extract,
        nb_mot=nb_mot,
        extract_ms=extract_ms,
        too_sparse=too_sparse,
        ocr_engine=ocr_engine,
    )


def build_feature_row(filename: str, raw_text: str, nb_mot: int) -> dict[str, object]:
    return {
        "text_2000": prepare_text_head(raw_text, TEXT_HEAD_CHARS),
        "filename_normalized": normalize_filename(filename),
        "nb_mot": nb_mot,
    }


def top5_probabilities(scored_row: pd.Series, model) -> tuple[TopClassProba, ...]:
    classes = list(model.classes_) if hasattr(model, "classes_") else []
    pairs: list[tuple[str, float]] = []
    for label in classes:
        col = f"p_{label}"
        if col in scored_row.index:
            pairs.append((label, float(scored_row[col])))
    pairs.sort(key=lambda x: -x[1])
    out: list[TopClassProba] = []
    for label, prob in pairs[:5]:
        out.append(TopClassProba(label=label, display_name=display_name_for_label(label), probability=prob))
    return tuple(out)


def _model_from_pipeline(pipeline):
    if hasattr(pipeline, "classes_"):
        return pipeline
    return pipeline.named_steps.get("clf", pipeline)


def model_class_count(model) -> int:
    inner = _model_from_pipeline(model)
    if hasattr(inner, "classes_"):
        return len(inner.classes_)
    return 0


def load_demo_artifacts(model_dir: Path | None = None):
    root = (model_dir or DEFAULT_OUTPUT_DIR).resolve()
    model = load_pipeline(root)
    tau, margin = load_thresholds(root)
    return model, tau, margin, root


@dataclass(frozen=True, slots=True)
class _LogregInferOutcome:
    infer_ms: float
    top5: tuple[TopClassProba, ...]
    pred_classifier: str
    pred_display: str
    decision: str
    decision_display: str
    routed_to_llm: bool
    accepted: bool
    max_proba: float
    margin: float
    passes_tau: bool
    passes_margin: bool


def _run_logreg_infer(
    model,
    row: dict[str, object],
    tau: float,
    margin_threshold: float,
) -> _LogregInferOutcome:
    t0 = time.perf_counter()
    scored = predict_frame(model, pd.DataFrame([row]))
    decision_series = apply_reject(scored, tau, margin_threshold)
    infer_ms = (time.perf_counter() - t0) * 1000.0
    s0 = scored.iloc[0]
    decision = str(decision_series.iloc[0])
    pred = str(s0["pred"])
    accepted = bool(accept_mask(scored, tau, margin_threshold).iloc[0])
    routed = decision == ROUTING_REJECT_LABEL
    max_proba = float(s0["max_proba"])
    margin_val = float(s0["margin"])
    return _LogregInferOutcome(
        infer_ms=infer_ms,
        top5=top5_probabilities(s0, model),
        pred_classifier=pred,
        pred_display=display_name_for_label(pred),
        decision=decision,
        decision_display=display_name_for_label(decision) if decision != ROUTING_REJECT_LABEL else ROUTING_REJECT_LABEL,
        routed_to_llm=routed,
        accepted=accepted,
        max_proba=max_proba,
        margin=margin_val,
        passes_tau=max_proba >= tau,
        passes_margin=margin_val >= margin_threshold,
    )


def _attach_llm_fields(
    *,
    llm: "DemoLlmResult | None",
    with_llm: bool,
    logreg_coarse: str | None,
) -> dict[str, object]:
    if not with_llm or llm is None:
        return {
            "with_llm": with_llm,
            "llm_label": None,
            "llm_coarse": None,
            "llm_display": None,
            "llm_coarse_display": None,
            "llm_model": None,
            "llm_ms": 0.0,
            "llm_error": None,
            "llm_prompt_tokens": None,
            "llm_completion_tokens": None,
            "logreg_llm_same_coarse": None,
        }
    coarse = llm.coarse
    same = None
    if llm.ok and logreg_coarse and coarse:
        same = logreg_coarse == coarse
    display = display_name_for_label(llm.label) if llm.label else None
    coarse_display = display_name_for_label(coarse) if coarse else None
    return {
        "with_llm": True,
        "llm_label": llm.label or None,
        "llm_coarse": coarse,
        "llm_display": display,
        "llm_coarse_display": coarse_display,
        "llm_model": llm.model,
        "llm_ms": llm.duration_ms,
        "llm_error": llm.error,
        "llm_prompt_tokens": llm.prompt_tokens if llm.ok else None,
        "llm_completion_tokens": llm.completion_tokens if llm.ok else None,
        "logreg_llm_same_coarse": same,
    }


def _merge_ocr_pipeline(
    base: DemoClassifyResult,
    ocr_pipe,
    *,
    pipelines_wall_ms: float,
) -> DemoClassifyResult:
    p1 = base.pipeline1_total_ms
    p2 = ocr_pipe.total_ms
    faster = None
    ratio = None
    if p1 > 0 and p2 > 0:
        faster = p1 < p2
        ratio = max(p1, p2) / min(p1, p2)

    llm = ocr_pipe.llm
    err = ocr_pipe.ocr_error
    if llm.error:
        err = f"{err or ''} {llm.error}".strip()

    preview = ocr_pipe.raw_text[:DEMO_RAW_PREVIEW_CHARS] if ocr_pipe.raw_text else None
    display = display_name_for_label(llm.label) if llm.label else None
    coarse_disp = display_name_for_label(llm.coarse) if llm.coarse else None

    fields = {
        "with_ocr_pipeline": True,
        "pipeline2_total_ms": p2,
        "pipeline2_ocr_ms": ocr_pipe.ocr_ms,
        "pipeline2_classify_ms": ocr_pipe.classify_ms,
        "pipeline2_wall_ms": ocr_pipe.wall_ms,
        "pipelines_wall_ms": pipelines_wall_ms,
        "pipeline2_label": llm.label or None,
        "pipeline2_display": display,
        "pipeline2_coarse": llm.coarse,
        "pipeline2_coarse_display": coarse_disp,
        "pipeline2_error": err,
        "pipeline2_raw_preview": preview,
        "pipeline2_nb_mot": ocr_pipe.nb_mot,
        "pipeline1_faster": faster,
        "pipeline_speed_ratio": ratio,
    }
    return replace(base, **fields)


def run_demo_classify(
    file_content: bytes,
    filename: str,
    *,
    model_dir: Path | None = None,
    model=None,
    tau: float | None = None,
    margin_threshold: float | None = None,
    infer_if_sparse: bool = False,
    with_llm: bool = False,
    with_ocr_pipeline: bool = False,
) -> DemoClassifyResult:
    if with_ocr_pipeline:
        from docia.file_processing.processor.classify.demo_ocr_pipeline import run_ocr_llm_pipeline

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_p1 = pool.submit(
                _run_pipeline_pymupdf_logreg,
                file_content,
                filename,
                model_dir=model_dir,
                model=model,
                tau=tau,
                margin_threshold=margin_threshold,
                infer_if_sparse=infer_if_sparse,
                with_llm=with_llm,
                pipeline1_conditional_mistral=True,
            )
            f_p2 = pool.submit(run_ocr_llm_pipeline, file_content, filename)
            base = f_p1.result()
            ocr_pipe = f_p2.result()
        wall = (time.perf_counter() - t0) * 1000.0
        return _merge_ocr_pipeline(base, ocr_pipe, pipelines_wall_ms=wall)

    return _run_pipeline_pymupdf_logreg(
        file_content,
        filename,
        model_dir=model_dir,
        model=model,
        tau=tau,
        margin_threshold=margin_threshold,
        infer_if_sparse=infer_if_sparse,
        with_llm=with_llm,
    )


def _run_pipeline_pymupdf_logreg(
    file_content: bytes,
    filename: str,
    *,
    model_dir: Path | None = None,
    model=None,
    tau: float | None = None,
    margin_threshold: float | None = None,
    infer_if_sparse: bool = False,
    with_llm: bool = False,
    pipeline1_conditional_mistral: bool = False,
) -> DemoClassifyResult:
    extract = extract_pdf_text_pymupdf4llm(file_content)
    raw_preview = extract.raw_text[:DEMO_RAW_PREVIEW_CHARS]
    fname_norm = normalize_filename(filename)
    sparse_warning = None
    if extract.too_sparse:
        sparse_warning = (
            f"Texte insuffisant ({extract.nb_mot} mots, seuil démo {DEMO_MIN_WORDS}). "
            "Texte très pauvre malgré l'extraction (PDF scanné ou illisible)."
        )

    skip_infer = extract.too_sparse and not infer_if_sparse
    row = build_feature_row(filename, extract.raw_text, extract.nb_mot)
    text_2000 = str(row["text_2000"])

    default_tau, default_margin = 0.95, 0.0
    if tau is None or margin_threshold is None:
        try:
            _, loaded_tau, loaded_margin, _ = load_demo_artifacts(model_dir)
            default_tau, default_margin = loaded_tau, loaded_margin
        except FileNotFoundError:
            pass
    tau = default_tau if tau is None else tau
    margin_threshold = default_margin if margin_threshold is None else margin_threshold

    if model is None and not skip_infer:
        model, _, _, _ = load_demo_artifacts(model_dir)

    from docia.file_processing.processor.classify.demo_llm import DemoLlmResult, classify_with_llm_demo

    logreg: _LogregInferOutcome | None = None
    llm: DemoLlmResult | None = None
    t_par = time.perf_counter()
    max_workers = (0 if skip_infer else 1) + (1 if with_llm else 0)
    max_workers = max(max_workers, 1)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures: dict[str, object] = {}
        if not skip_infer and model is not None:
            futures["logreg"] = pool.submit(_run_logreg_infer, model, row, tau, margin_threshold)
        if with_llm:
            futures["llm"] = pool.submit(classify_with_llm_demo, filename, extract.raw_text)

        for name, fut in futures.items():
            outcome = fut.result()
            if name == "logreg":
                logreg = outcome
            else:
                llm = outcome

    parallel_infer_ms = (time.perf_counter() - t_par) * 1000.0
    infer_ms = logreg.infer_ms if logreg else 0.0
    total_ms = extract.extract_ms + parallel_infer_ms

    if skip_infer:
        llm_extra = _attach_llm_fields(llm=llm, with_llm=with_llm, logreg_coarse=None)
        return DemoClassifyResult(
            filename=filename,
            filename_normalized=fname_norm,
            raw_text_preview=raw_preview,
            text_2000=text_2000,
            nb_mot=extract.nb_mot,
            nb_pages=extract.nb_pages,
            pages_extracted=extract.pages_extracted,
            top5=(),
            pred_classifier="",
            pred_display="",
            decision=ROUTING_REJECT_LABEL,
            decision_display=ROUTING_REJECT_LABEL,
            routed_to_llm=True,
            accepted=False,
            tau=tau,
            margin_threshold=margin_threshold,
            max_proba=0.0,
            margin=0.0,
            passes_tau=False,
            passes_margin=False,
            model_n_classes=model_class_count(model) if model is not None else 0,
            extract_ms=extract.extract_ms,
            infer_ms=0.0,
            total_ms=total_ms,
            too_sparse=True,
            sparse_warning=sparse_warning,
            inference_skipped=True,
            parallel_infer_ms=parallel_infer_ms,
            pipeline1_total_ms=extract.extract_ms,
            extract_ocr_engine=extract.ocr_engine,
            **llm_extra,
        )

    assert logreg is not None
    logreg_coarse = logreg.decision if logreg.accepted else logreg.pred_classifier
    llm_extra = _attach_llm_fields(llm=llm, with_llm=with_llm, logreg_coarse=logreg_coarse)

    mistral_extra: dict[str, object] = {}
    if pipeline1_conditional_mistral:
        mistral_extra = _conditional_pipeline1_post_logreg_ocr(file_content, logreg)

    pipeline1_total = extract.extract_ms + infer_ms + float(mistral_extra.get("pipeline1_post_logreg_ocr_ms", 0.0))

    return DemoClassifyResult(
        filename=filename,
        filename_normalized=fname_norm,
        raw_text_preview=raw_preview,
        text_2000=text_2000,
        nb_mot=extract.nb_mot,
        nb_pages=extract.nb_pages,
        pages_extracted=extract.pages_extracted,
        top5=logreg.top5,
        pred_classifier=logreg.pred_classifier,
        pred_display=logreg.pred_display,
        decision=logreg.decision,
        decision_display=logreg.decision_display,
        routed_to_llm=logreg.routed_to_llm,
        accepted=logreg.accepted,
        tau=tau,
        margin_threshold=margin_threshold,
        max_proba=logreg.max_proba,
        margin=logreg.margin,
        passes_tau=logreg.passes_tau,
        passes_margin=logreg.passes_margin,
        model_n_classes=model_class_count(model),
        extract_ms=extract.extract_ms,
        infer_ms=infer_ms,
        total_ms=total_ms,
        too_sparse=extract.too_sparse,
        sparse_warning=sparse_warning if extract.too_sparse else None,
        inference_skipped=False,
        parallel_infer_ms=parallel_infer_ms,
        pipeline1_total_ms=pipeline1_total,
        extract_ocr_engine=extract.ocr_engine,
        **llm_extra,
        **mistral_extra,
    )