from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from docia.file_processing.processor.classify.constants import DEFAULT_OUTPUT_DIR
from docia.file_processing.processor.classify.label_hierarchy import HIERARCHY_REVISION, map_llm_to_coarse

logger = logging.getLogger(__name__)

DEFAULT_REVIEW_SOURCES = (
    "01_annotation_audit_sample.csv",
    "06_disagreement_review_train_val_calib.csv",
    "08_below_median_disagreement_review_sample.csv",
    "09_non_target_trio_review_sample.csv",
    "10_core_four_miss_review_sample.csv",
)


def export_silver_corrections(
    output_dir: Path | None = None,
    *,
    sources: tuple[str, ...] = DEFAULT_REVIEW_SOURCES,
) -> Path:
    """Fusionne les revues ``review_ok=non`` (erreur silver LLM) pour le prochain train."""
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    rep = output_dir / "reports"
    parts: list[pd.DataFrame] = []
    for name in sources:
        path = rep / name
        if not path.is_file():
            logger.warning("Skip missing review file: %s", path)
            continue
        df = pd.read_csv(path)
        if "review_ok" not in df.columns or "id" not in df.columns:
            continue
        v = df["review_ok"].fillna("").astype(str).str.strip().str.lower()
        m = v.isin(["non", "no", "false", "0"])
        sub = df.loc[m].copy()
        if sub.empty:
            continue
        sub["review_source"] = name
        parts.append(sub)

    if not parts:
        raise RuntimeError("No LLM-error reviews (review_ok=non) found in sources")

    merged = pd.concat(parts, ignore_index=True)
    merged["id"] = merged["id"].astype(str)
    merged = merged.sort_values(["id", "review_source"]).drop_duplicates(subset=["id"], keep="last")

    fine = merged.get("review_correct_label", merged.get("classification", pd.Series(dtype=str)))
    merged["label_train_coarse"] = fine.map(lambda x: map_llm_to_coarse(x) if pd.notna(x) else None)

    out = rep / "11_silver_corrections_for_train.csv"
    merged.to_csv(out, index=False)
    meta = rep / "11_silver_corrections_summary.md"
    mapped = merged["label_train_coarse"].notna().sum()
    meta.write_text(
        f"# Silver corrections\n\n"
        f"hierarchy_revision: {HIERARCHY_REVISION}\n"
        f"unique_ids: {len(merged)}\n"
        f"coarse_mapped: {mapped}\n"
        f"unmapped_fine: {len(merged) - mapped}\n",
        encoding="utf-8",
    )
    return out