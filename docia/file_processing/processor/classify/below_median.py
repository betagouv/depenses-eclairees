from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from docia.documents.models import Document
from docia.file_processing.processor.classify.artifacts import load_pipeline
from docia.file_processing.processor.classify.constants import (
    CLASSIFIER_ARTIFACT_NAME,
    TARGET_CLASSES,
    TARGET_RATIO_MEDIAN,
    THRESHOLD_ARTIFACT_NAME,
)
from docia.file_processing.processor.classify.dataset import (
    MEDIAN_SAMPLE_CHUNK,
    ROW_BATCH_SIZE,
    _LIGHT_FIELDS,
    _compute_medians_from_db,
    _load_texts_map,
    _passes_ratio_median_light,
    _row_from_light,
)
from docia.file_processing.processor.classify.evaluate import apply_reject, predict_frame
from docia.file_processing.processor.classify.fill_ratio import compute_ratio_data_extraction

logger = logging.getLogger(__name__)


@dataclass
class BelowMedianStats:
    scanned: int = 0
    excluded_below_median: int = 0
    scored: int = 0
    skipped_empty_text: int = 0
    by_class: Counter = field(default_factory=Counter)


def load_medians_by_class(output_dir: Path, *, recompute: bool = False) -> dict[str, float]:
    if not recompute:
        manifest = output_dir / "dataset_manifest.json"
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            medians = data.get("medians_by_class")
            if medians:
                return {str(k): float(v) for k, v in medians.items()}
    logger.info("Computing medians from database (same rule as dataset build)")
    return _compute_medians_from_db()


def load_thresholds(output_dir: Path) -> tuple[float, float]:
    path = output_dir / THRESHOLD_ARTIFACT_NAME
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data["tau"]), float(data["margin"])
    return 0.95, 0.0


def _rows_to_frame(
    batch: list[dict[str, Any]],
    texts: dict[str, str],
    medians: dict[str, float],
    stats: BelowMedianStats,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in batch:
        row = _row_from_light(item, texts.get(str(item["id"]), ""), None, "below_median_excluded")
        if not (row["text_2000"] or "").strip():
            stats.skipped_empty_text += 1
            continue
        cls = row["classification"]
        med = medians.get(cls)
        row["median_ratio_class"] = med
        row["ratio_below_median"] = med is not None and float(row["ratio_extracted"] or 0) < float(med)
        rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _append_parquet(path: Path, df: pd.DataFrame) -> None:
    if "median_ratio_class" in df.columns:
        df = df.copy()
        df["median_ratio_class"] = pd.to_numeric(df["median_ratio_class"], errors="coerce")
    table = pa.Table.from_pandas(df, preserve_index=False)
    if path.is_file():
        existing = pq.read_table(path)
        table = pa.concat_tables([existing, table])
    pq.write_table(table, path)


def _write_summary(path: Path, df: pd.DataFrame, tau: float, margin: float) -> None:
    rows: list[dict[str, Any]] = []
    for cls, sub in df.groupby("classification", dropna=False):
        n = len(sub)
        agree = sub["agree_llm_logreg"].mean() if n else 0.0
        reject = (sub["logreg_pred_with_reject"] == "Non classifié").mean() if n else 0.0
        rows.append(
            {
                "classification": cls,
                "n": n,
                "agreement_rate_llm_vs_logreg": round(float(agree), 4),
                "logreg_reject_rate": round(float(reject), 4),
                "mean_max_proba": round(float(sub["max_proba"].mean()), 4) if n else None,
                "mean_ratio_extracted": round(float(sub["ratio_extracted"].mean()), 4) if n else None,
            }
        )
    overall = pd.DataFrame(rows).sort_values("n", ascending=False)
    overall.to_csv(path, index=False)
    meta = path.with_suffix(".md")
    meta.write_text(
        f"# Below-median scoring\n\n"
        f"Rows: {len(df)}\n"
        f"tau={tau}, margin={margin}\n"
        f"Overall agreement (LLM vs logreg): "
        f"{df['agree_llm_logreg'].mean():.4f}\n",
        encoding="utf-8",
    )


def run_below_median_scoring(
    output_dir: Path,
    *,
    out_path: Path | None = None,
    max_rows: int | None = None,
    recompute_medians: bool = False,
    tau: float | None = None,
    margin: float | None = None,
    summary_path: Path | None = None,
) -> tuple[Path, BelowMedianStats]:
    """Exporte depuis la DB les docs sous la médiane ratio, les score avec le pipeline V2."""
    output_dir = output_dir.resolve()
    artifact = output_dir / CLASSIFIER_ARTIFACT_NAME
    if not artifact.is_file():
        raise FileNotFoundError(f"Missing classifier at {artifact}")

    medians = load_medians_by_class(output_dir, recompute=recompute_medians)
    default_tau, default_margin = load_thresholds(output_dir)
    tau = default_tau if tau is None else tau
    margin = default_margin if margin is None else margin

    model = load_pipeline(output_dir)
    out_path = out_path or (output_dir / "below_median_scored.parquet")
    if out_path.is_file():
        out_path.unlink()
    summary_path = summary_path or (output_dir / "reports" / "07_below_median_summary.csv")

    stats = BelowMedianStats()
    batch: list[dict[str, Any]] = []
    done = False

    def flush_batch() -> None:
        nonlocal done
        if not batch or done:
            batch.clear()
            return
        texts = _load_texts_map([i["id"] for i in batch])
        frame = _rows_to_frame(batch, texts, medians, stats)
        batch.clear()
        if frame.empty:
            return
        if max_rows is not None and stats.scored + len(frame) > max_rows:
            frame = frame.iloc[: max_rows - stats.scored]
            done = True
        scored = predict_frame(model, frame)
        scored["logreg_pred"] = scored["pred"]
        scored["logreg_pred_with_reject"] = apply_reject(scored, tau, margin)
        scored["llm_pred"] = scored["classification"]
        scored["agree_llm_logreg"] = scored["llm_pred"].astype(str) == scored["logreg_pred"].astype(str)
        scored["in_target_eight"] = scored["classification"].isin(TARGET_CLASSES)
        slim = scored[
            [
                "id",
                "hash",
                "filename",
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
                "ratio_below_median",
                "in_target_eight",
                "nb_mot",
            ]
        ].copy()
        _append_parquet(out_path, slim)
        stats.scored += len(slim)
        for cls in slim["classification"].astype(str):
            stats.by_class[cls] += 1
        logger.info("Scored below-median rows: %s", stats.scored)

    qs = (
        Document.objects.filter(classification__in=TARGET_RATIO_MEDIAN)
        .exclude(analyzed_at__isnull=True)
        .exclude(text__isnull=True)
        .exclude(text="")
        .values(*_LIGHT_FIELDS)
        .iterator(chunk_size=MEDIAN_SAMPLE_CHUNK)
    )
    for item in qs:
        if done:
            break
        stats.scanned += 1
        ratio = compute_ratio_data_extraction(item["structured_data"])
        if _passes_ratio_median_light(item["classification"], ratio, item.get("analyzed_at"), medians):
            continue
        stats.excluded_below_median += 1
        batch.append(item)
        if len(batch) >= ROW_BATCH_SIZE:
            flush_batch()
        if max_rows is not None and stats.scored >= max_rows:
            done = True
            break

    flush_batch()

    if not out_path.is_file():
        raise RuntimeError("No below-median rows scored (empty export)")

    full = pd.read_parquet(out_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    _write_summary(summary_path, full, tau, margin)
    disagree_path = summary_path.with_name("07_below_median_disagreements.csv")
    disagree = full.loc[~full["agree_llm_logreg"]].sort_values("max_proba", ascending=False)
    disagree.to_csv(disagree_path, index=False)
    logger.info(
        "Below median: scanned=%s excluded=%s scored=%s agreement=%.3f -> %s",
        stats.scanned,
        stats.excluded_below_median,
        stats.scored,
        full["agree_llm_logreg"].mean(),
        out_path,
    )
    return out_path, stats