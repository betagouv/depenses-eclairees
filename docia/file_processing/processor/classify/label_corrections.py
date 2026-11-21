from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from docia.file_processing.processor.classify.constants import (
    ANNEXE_FINANCIERE_LABEL,
    FINANCIAL_TARGETS,
    TARGET_CLASSES,
)
from docia.file_processing.processor.classify.label_hierarchy import TRAINABLE_COARSE, map_llm_to_coarse

logger = logging.getLogger(__name__)

TRAINABLE_LABELS = TARGET_CLASSES | {ANNEXE_FINANCIERE_LABEL}


def map_review_correct_label(
    label: str | None,
    *,
    merge_financial: bool,
    coarse_hierarchy: bool = False,
) -> str | None:
    if not label or (isinstance(label, float) and pd.isna(label)):
        return None
    text = str(label).strip()
    if not text or text.lower() == "nan":
        return None
    if coarse_hierarchy:
        return map_llm_to_coarse(text)
    if merge_financial and text in FINANCIAL_TARGETS:
        return ANNEXE_FINANCIERE_LABEL
    if text == ANNEXE_FINANCIERE_LABEL or text in TARGET_CLASSES:
        return text
    return None


def apply_coarse_hierarchy_labels(df: pd.DataFrame) -> int:
    """Réécrit label_train à partir de classification via label_hierarchy."""
    mapped = df["classification"].map(map_llm_to_coarse)
    mask = mapped.notna()
    n = int(mask.sum())
    df.loc[mask, "label_train"] = mapped[mask]
    return n


def trainable_label_set(*, coarse_hierarchy: bool) -> frozenset[str]:
    if coarse_hierarchy:
        return TRAINABLE_COARSE
    return TRAINABLE_LABELS


def apply_annexe_financiere_merge(df: pd.DataFrame) -> int:
    mask = df["label_train"].isin(FINANCIAL_TARGETS)
    n = int(mask.sum())
    if n:
        df.loc[mask, "label_train"] = ANNEXE_FINANCIERE_LABEL
    return n


def apply_disagreement_reviews(
    df: pd.DataFrame,
    review_csv: Path,
    *,
    merge_financial: bool,
    coarse_hierarchy: bool = False,
) -> dict[str, int]:
    reviews = pd.read_csv(review_csv)
    stats = {"rows_in_csv": len(reviews), "updated": 0, "excluded_from_train": 0, "skipped": 0, "missing_id": 0}
    id_to_idx = df.index[df["id"].astype(str).duplicated(keep=False)]
    if len(id_to_idx):
        logger.warning("Duplicate ids in parquet: %s", len(id_to_idx))

    for _, row in reviews.iterrows():
        verdict = str(row.get("review_ok", "")).strip().lower()
        if verdict not in ("non", "no", "false", "0"):
            stats["skipped"] += 1
            continue
        correct = row.get("review_correct_label")
        mapped = map_review_correct_label(
            correct, merge_financial=merge_financial, coarse_hierarchy=coarse_hierarchy
        )
        doc_id = str(row["id"])
        hit = df["id"].astype(str) == doc_id
        if not hit.any():
            stats["missing_id"] += 1
            continue
        if mapped is None:
            df.loc[hit, "label_train"] = pd.NA
            stats["excluded_from_train"] += int(hit.sum())
            logger.info("Review exclude id=%s correct_label=%r (hors cibles)", doc_id, correct)
        else:
            df.loc[hit, "label_train"] = mapped
            stats["updated"] += int(hit.sum())
    return stats