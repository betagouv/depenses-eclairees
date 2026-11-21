from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from docia.documents.models import Document
from docia.file_processing.processor.classify.artifacts import load_pipeline
from docia.file_processing.processor.classify.below_median import (
    load_medians_by_class,
    load_thresholds,
)
from docia.file_processing.processor.classify.constants import (
    CLASSIFIER_ARTIFACT_NAME,
    CORE_FOUR_MISSED_TRACKING,
    TARGET_CLASSES,
    TARGET_RATIO_MEDIAN,
)
from docia.file_processing.processor.classify.core_four_tracking import OTHER_TARGET_CLASSES
from docia.file_processing.processor.classify.dataset import (
    MEDIAN_SAMPLE_CHUNK,
    ROW_BATCH_SIZE,
    _LIGHT_FIELDS,
    _ej_map_for_ids,
    _load_texts_map,
    _passes_ratio_median_light,
    _row_from_light,
)
from docia.file_processing.processor.classify.evaluate import apply_reject, predict_frame
from docia.file_processing.processor.classify.fill_ratio import compute_ratio_data_extraction

logger = logging.getLogger(__name__)

# Trio financier (modèle 8 classes) + cctp côté LLM pour audits annexes
FINANCIAL_TRIO_MODEL = frozenset({"devis", "bordereau_prix", "detail_quantitatif_estimatif"})
FINANCIAL_TRIO_LLM = FINANCIAL_TRIO_MODEL | frozenset({"cctp"})

OUTPUT_COLUMNS = [
    "id",
    "hash",
    "filename",
    "num_ej",
    "classification",
    "llm_pred",
    "label_train",
    "logreg_pred",
    "logreg_pred_with_reject",
    "max_proba",
    "margin",
    "agree_llm_logreg",
    "ratio_extracted",
    "median_ratio_class",
    "in_target_eight",
    "scoring_cohort",
    "llm_in_financial_trio",
    "logreg_in_financial_trio",
    "llm_missed_financial_trio",
    "nb_mot",
]


@dataclass
class ScoringRunStats:
    scanned: int = 0
    scored: int = 0
    skipped_empty_text: int = 0
    by_llm_class: Counter = field(default_factory=Counter)
    trio_flags: int = 0


def _canonicalize_scored_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "median_ratio_class" in out.columns:
        out["median_ratio_class"] = pd.to_numeric(out["median_ratio_class"], errors="coerce")
    if "label_train" in out.columns:
        out["label_train"] = out["label_train"].where(out["label_train"].notna(), None)
    if "num_ej" in out.columns:
        out["num_ej"] = out["num_ej"].fillna("").astype(str)
    return out


def _append_parquet(path: Path, df: pd.DataFrame) -> None:
    df = _canonicalize_scored_frame(df)
    table = pa.Table.from_pandas(df, preserve_index=False)
    if path.is_file():
        existing = pq.read_table(path)
        table = pa.concat_tables([existing, table])
    pq.write_table(table, path)


def _prepare_frame(
    batch: list[dict[str, Any]],
    texts: dict[str, str],
    ej_map: dict[str, str],
    medians: dict[str, float],
    cohort: str,
    stats: ScoringRunStats,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in batch:
        row = _row_from_light(item, texts.get(str(item["id"]), ""), ej_map.get(str(item["id"])), cohort)
        if not (row["text_2000"] or "").strip():
            stats.skipped_empty_text += 1
            continue
        cls = row["classification"]
        med = medians.get(cls)
        row["median_ratio_class"] = med
        row["scoring_cohort"] = cohort
        rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _annotate_and_slim(scored: pd.DataFrame, tau: float, margin: float, cohort: str) -> pd.DataFrame:
    scored["logreg_pred"] = scored["pred"]
    scored["logreg_pred_with_reject"] = apply_reject(scored, tau, margin)
    scored["llm_pred"] = scored["classification"]
    scored["num_ej"] = scored["num_ej"].fillna("").astype(str)
    scored["agree_llm_logreg"] = scored["llm_pred"].astype(str) == scored["logreg_pred"].astype(str)
    scored["in_target_eight"] = scored["classification"].isin(TARGET_CLASSES)
    scored["scoring_cohort"] = cohort
    scored["llm_in_financial_trio"] = scored["llm_pred"].isin(FINANCIAL_TRIO_LLM)
    scored["logreg_in_financial_trio"] = scored["logreg_pred"].isin(FINANCIAL_TRIO_MODEL)
    accepted = scored["logreg_pred_with_reject"] != "Non classifié"
    scored["llm_missed_financial_trio"] = (
        ~scored["llm_pred"].isin(FINANCIAL_TRIO_LLM)
        & scored["logreg_in_financial_trio"]
        & accepted
    )
    scored["llm_in_core_four"] = scored["llm_pred"].isin(CORE_FOUR_MISSED_TRACKING)
    scored["logreg_in_core_four"] = scored["logreg_pred"].isin(CORE_FOUR_MISSED_TRACKING)
    scored["llm_missed_core_four"] = (
        ~scored["llm_in_core_four"] & scored["logreg_in_core_four"] & accepted
    )
    scored = scored.drop(columns=["pred", "text_2000", "filename_normalized"], errors="ignore")
    cols = [c for c in OUTPUT_COLUMNS if c in scored.columns]
    return scored[cols].copy()


def _run_stream(
    items: Iterator[dict[str, Any]],
    *,
    output_dir: Path,
    out_path: Path,
    cohort: str,
    medians: dict[str, float],
    model,
    tau: float,
    margin: float,
    stats: ScoringRunStats,
    max_rows: int | None,
) -> None:
    batch: list[dict[str, Any]] = []
    done = False

    def flush() -> None:
        nonlocal done, batch
        if not batch or done:
            batch.clear()
            return
        ids = [i["id"] for i in batch]
        texts = _load_texts_map(ids)
        ej_map = _ej_map_for_ids([str(i) for i in ids])
        frame = _prepare_frame(batch, texts, ej_map, medians, cohort, stats)
        batch.clear()
        if frame.empty:
            return
        if max_rows is not None and stats.scored + len(frame) > max_rows:
            frame = frame.iloc[: max_rows - stats.scored]
            done = True
        scored = predict_frame(model, frame)
        slim = _annotate_and_slim(scored, tau, margin, cohort)
        _append_parquet(out_path, slim)
        stats.scored += len(slim)
        stats.trio_flags += int(slim["llm_missed_financial_trio"].sum())
        for cls in slim["classification"].astype(str):
            stats.by_llm_class[cls] += 1
        logger.info("[%s] scored=%s trio_missed=%s", cohort, stats.scored, stats.trio_flags)

    for item in items:
        if done:
            break
        stats.scanned += 1
        batch.append(item)
        if len(batch) >= ROW_BATCH_SIZE:
            flush()
        if max_rows is not None and stats.scored >= max_rows:
            done = True
            break
    flush()


def _write_non_target_reports(output_dir: Path, df: pd.DataFrame, tau: float, margin: float) -> None:
    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)

    rows = []
    for cls, sub in df.groupby("classification", dropna=False):
        n = len(sub)
        rows.append(
            {
                "classification": cls,
                "n": n,
                "agreement_rate": round(float(sub["agree_llm_logreg"].mean()), 4) if n else 0.0,
                "logreg_reject_rate": round(float((sub["logreg_pred_with_reject"] == "Non classifié").mean()), 4),
                "llm_missed_trio_rate": round(float(sub["llm_missed_financial_trio"].mean()), 4),
                "mean_max_proba": round(float(sub["max_proba"].mean()), 4) if n else None,
            }
        )
    pd.DataFrame(rows).sort_values("n", ascending=False).to_csv(rep / "09_non_target_llm_summary.csv", index=False)

    trio = df.loc[df["llm_missed_financial_trio"]].sort_values("max_proba", ascending=False)
    trio.to_csv(rep / "09_llm_missed_financial_trio.csv", index=False)

    cctp = df.loc[df["classification"] == "cctp"].copy()
    if not cctp.empty:
        cctp_fin = cctp[cctp["logreg_pred"].isin(FINANCIAL_TRIO_MODEL)].sort_values("max_proba", ascending=False)
        cctp_fin.to_csv(rep / "09_cctp_logreg_financial.csv", index=False)

    (rep / "09_non_target_llm_summary.md").write_text(
        f"# Non-target LLM scoring\n\nRows: {len(df)}\ntau={tau}, margin={margin}\n"
        f"Agreement: {df['agree_llm_logreg'].mean():.4f}\n"
        f"LLM missed financial trio (logreg accept): {len(trio)} ({trio.shape[0]/len(df):.4f})\n",
        encoding="utf-8",
    )


def run_non_target_llm_scoring(
    output_dir: Path,
    *,
    out_path: Path | None = None,
    max_rows: int | None = None,
    tau: float | None = None,
    margin: float | None = None,
) -> tuple[Path, ScoringRunStats]:
    """
    Score tous les documents dont la classification LLM est hors des 8 cibles d'entraînement.
    Détecte les cas où la logreg voit devis / BPU / DQE alors que le LLM a « rejeté » (autre type).
    """
    output_dir = output_dir.resolve()
    artifact = output_dir / CLASSIFIER_ARTIFACT_NAME
    if not artifact.is_file():
        raise FileNotFoundError(f"Missing classifier at {artifact}")

    medians = load_medians_by_class(output_dir)
    default_tau, default_margin = load_thresholds(output_dir)
    tau = default_tau if tau is None else tau
    margin = default_margin if margin is None else margin
    model = load_pipeline(output_dir)

    out_path = out_path or (output_dir / "non_target_llm_scored.parquet")
    if out_path.is_file():
        out_path.unlink()

    stats = ScoringRunStats()
    qs = (
        Document.objects.exclude(classification__in=TARGET_CLASSES)
        .exclude(classification__isnull=True)
        .exclude(classification="")
        .exclude(text__isnull=True)
        .exclude(text="")
        .order_by("id")
        .values(*_LIGHT_FIELDS)
        .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
    )
    _run_stream(
        qs,
        output_dir=output_dir,
        out_path=out_path,
        cohort="non_target_llm",
        medians=medians,
        model=model,
        tau=tau,
        margin=margin,
        stats=stats,
        max_rows=max_rows,
    )
    if not out_path.is_file():
        raise RuntimeError("No non-target rows scored")

    full = pd.read_parquet(out_path)
    _write_non_target_reports(output_dir, full, tau, margin)
    disagree = full.loc[~full["agree_llm_logreg"]].sort_values("max_proba", ascending=False)
    disagree.to_csv(output_dir / "reports" / "09_non_target_disagreements.csv", index=False)
    logger.info(
        "Non-target LLM: scanned=%s scored=%s agreement=%.3f trio_missed=%s -> %s",
        stats.scanned,
        stats.scored,
        full["agree_llm_logreg"].mean(),
        int(full["llm_missed_financial_trio"].sum()),
        out_path,
    )
    return out_path, stats


def run_other_target_llm_scoring(
    output_dir: Path,
    *,
    out_path: Path | None = None,
    max_rows: int | None = None,
    tau: float | None = None,
    margin: float | None = None,
) -> tuple[Path, ScoringRunStats]:
    """Score les 4 autres cibles d'entraînement (avenant, devis, BPU, DQE) pour oublis core-four."""
    output_dir = output_dir.resolve()
    artifact = output_dir / CLASSIFIER_ARTIFACT_NAME
    if not artifact.is_file():
        raise FileNotFoundError(f"Missing classifier at {artifact}")

    medians = load_medians_by_class(output_dir)
    default_tau, default_margin = load_thresholds(output_dir)
    tau = default_tau if tau is None else tau
    margin = default_margin if margin is None else margin
    model = load_pipeline(output_dir)

    out_path = out_path or (output_dir / "other_target_llm_scored.parquet")
    if out_path.is_file():
        out_path.unlink()

    stats = ScoringRunStats()
    qs = (
        Document.objects.filter(classification__in=OTHER_TARGET_CLASSES)
        .exclude(text__isnull=True)
        .exclude(text="")
        .order_by("id")
        .values(*_LIGHT_FIELDS)
        .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
    )
    _run_stream(
        qs,
        output_dir=output_dir,
        out_path=out_path,
        cohort="other_target_llm",
        medians=medians,
        model=model,
        tau=tau,
        margin=margin,
        stats=stats,
        max_rows=max_rows,
    )
    if not out_path.is_file():
        raise RuntimeError("No other-target rows scored")
    logger.info("Other-target LLM: scanned=%s scored=%s -> %s", stats.scanned, stats.scored, out_path)
    return out_path, stats


def run_below_median_scoring_v2(
    output_dir: Path,
    *,
    out_path: Path | None = None,
    max_rows: int | None = None,
    recompute_medians: bool = False,
    tau: float | None = None,
    margin: float | None = None,
) -> tuple[Path, ScoringRunStats]:
    """Même périmètre que below_median.py mais avec num_ej et flags trio financier."""
    output_dir = output_dir.resolve()
    medians = load_medians_by_class(output_dir, recompute=recompute_medians)
    default_tau, default_margin = load_thresholds(output_dir)
    tau = default_tau if tau is None else tau
    margin = default_margin if margin is None else margin
    model = load_pipeline(output_dir)
    out_path = out_path or (output_dir / "below_median_scored.parquet")
    if out_path.is_file():
        out_path.unlink()

    stats = ScoringRunStats()

    def iter_below() -> Iterator[dict[str, Any]]:
        qs = (
            Document.objects.filter(classification__in=TARGET_RATIO_MEDIAN)
            .exclude(analyzed_at__isnull=True)
            .exclude(text__isnull=True)
            .exclude(text="")
            .values(*_LIGHT_FIELDS)
            .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
        )
        for item in qs:
            ratio = compute_ratio_data_extraction(item["structured_data"])
            if _passes_ratio_median_light(item["classification"], ratio, item.get("analyzed_at"), medians):
                continue
            yield item

    _run_stream(
        iter_below(),
        output_dir=output_dir,
        out_path=out_path,
        cohort="below_median",
        medians=medians,
        model=model,
        tau=tau,
        margin=margin,
        stats=stats,
        max_rows=max_rows,
    )
    if not out_path.is_file():
        raise RuntimeError("No below-median rows scored")
    from docia.file_processing.processor.classify.below_median import _write_summary

    full = pd.read_parquet(out_path)
    _write_summary(output_dir / "reports" / "07_below_median_summary.csv", full, tau, margin)
    disagree = full.loc[~full["agree_llm_logreg"]].sort_values("max_proba", ascending=False)
    disagree.to_csv(output_dir / "reports" / "07_below_median_disagreements.csv", index=False)
    return out_path, stats