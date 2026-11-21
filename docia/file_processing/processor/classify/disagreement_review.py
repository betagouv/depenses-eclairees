from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from docia.file_processing.processor.classify.constants import CONFUSION_PAIRS, DEFAULT_OUTPUT_DIR, TARGET_CLASSES
from docia.file_processing.processor.classify.dataset import (
    TEXT_FETCH_CHUNK,
    _chunked,
    _ej_map_for_ids,
    _load_texts_map,
)
from docia.file_processing.processor.classify.text_prep import normalize_filename, prepare_text_head
from docia.file_processing.processor.classify.constants import TEXT_HEAD_CHARS

logger = logging.getLogger(__name__)

REVIEW_COLUMNS = (
    "id",
    "hash",
    "filename",
    "num_ej",
    "nb_mot",
    "text_2000",
    "filename_normalized",
    "llm_pred",
    "logreg_pred",
    "logreg_pred_with_reject",
    "max_proba",
    "margin",
    "ratio_extracted",
    "median_ratio_class",
    "review_ok",
    "review_correct_label",
    "review_notes",
)


def _attach_review_context(df: pd.DataFrame) -> pd.DataFrame:
    ids = df["id"].astype(str).tolist()
    texts: dict[str, str] = {}
    for chunk in _chunked(ids, TEXT_FETCH_CHUNK):
        texts.update(_load_texts_map(chunk))
    ej_map = _ej_map_for_ids(ids)
    out = df.copy()
    out["text_2000"] = out["id"].astype(str).map(lambda i: prepare_text_head(texts.get(i, ""), TEXT_HEAD_CHARS))
    out["filename_normalized"] = out["filename"].fillna("").map(normalize_filename)
    out["num_ej"] = out["id"].astype(str).map(lambda i: ej_map.get(i) or "")
    return out


def _priority_score(row: pd.Series) -> float:
    """Haut = bon candidat pour erreur LLM (logreg confiante et acceptée)."""
    prob = float(row.get("max_proba") or 0)
    margin = float(row.get("margin") or 0)
    rejected = row.get("logreg_pred_with_reject") == "Non classifié"
    boost = 0.0 if rejected else 0.05
    pair = (str(row["llm_pred"]), str(row["logreg_pred"]))
    if pair in CONFUSION_PAIRS or (pair[1], pair[0]) in CONFUSION_PAIRS:
        boost += 0.02
    return prob + 0.25 * margin + boost


def sample_disagreements_for_review(
    disagree_df: pd.DataFrame,
    *,
    per_pair: int = 20,
    max_total: int | None = 500,
    min_max_proba: float = 0.85,
    require_logreg_accept: bool = True,
    only_target_llm: bool = True,
) -> pd.DataFrame:
    df = disagree_df.loc[~disagree_df["agree_llm_logreg"]].copy()
    if only_target_llm:
        df = df[df["llm_pred"].isin(TARGET_CLASSES)]
    if require_logreg_accept:
        df = df[df["logreg_pred_with_reject"] != "Non classifié"]
    df = df[df["max_proba"] >= min_max_proba]
    if df.empty:
        return df
    df["_priority"] = df.apply(_priority_score, axis=1)
    df["pair_key"] = df["llm_pred"].astype(str) + " -> " + df["logreg_pred"].astype(str)

    parts: list[pd.DataFrame] = []
    for _, sub in df.groupby(["llm_pred", "logreg_pred"], dropna=False):
        parts.append(sub.sort_values("_priority", ascending=False).head(per_pair))
    sample = pd.concat(parts, ignore_index=True).sort_values("_priority", ascending=False)
    if max_total is not None and len(sample) > max_total:
        sample = sample.head(max_total)
    return sample.drop(columns=["_priority", "pair_key"], errors="ignore")


def export_non_target_trio_review(
    output_dir: Path | None = None,
    *,
    scored_parquet: Path | None = None,
    per_pair: int = 15,
    max_total: int = 400,
    with_text: bool = True,
) -> Path:
    """Échantillon pour revue: LLM hors trio financier, logreg accepte devis/BPU/DQE."""
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    scored_path = scored_parquet or (output_dir / "non_target_llm_scored.parquet")
    full = pd.read_parquet(scored_path)
    pool = full.loc[full["llm_missed_financial_trio"]].copy()
    if pool.empty:
        raise RuntimeError("No llm_missed_financial_trio rows in parquet")
    pool["_priority"] = pool["max_proba"] + 0.25 * pool["margin"]
    parts = []
    for _, sub in pool.groupby(["llm_pred", "logreg_pred"], dropna=False):
        parts.append(sub.sort_values("_priority", ascending=False).head(per_pair))
    sample = pd.concat(parts, ignore_index=True).sort_values("_priority", ascending=False)
    if len(sample) > max_total:
        sample = sample.head(max_total)
    sample = sample.drop(columns=["_priority"], errors="ignore")
    if with_text and not sample.empty:
        sample = _attach_review_context(sample)
    for col in ("review_ok", "review_correct_label", "review_notes"):
        if col not in sample.columns:
            sample[col] = ""
    if "num_ej" in sample.columns:
        sample["num_ej"] = sample["num_ej"].fillna("").astype(str)
    out_path = output_dir / "reports" / "09_non_target_trio_review_sample.csv"
    cols = [c for c in REVIEW_COLUMNS if c in sample.columns]
    sample[cols].to_csv(out_path, index=False)
    return out_path


def export_below_median_disagreement_review(
    output_dir: Path | None = None,
    *,
    scored_parquet: Path | None = None,
    per_pair: int = 20,
    max_total: int = 500,
    min_max_proba: float = 0.85,
    require_logreg_accept: bool = True,
    full_unsampled: bool = False,
    with_text: bool = True,
) -> tuple[Path, Path]:
    """CSV prêt pour revue humaine (traquer erreurs LLM sur pool sous-médiane)."""
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    scored_path = scored_parquet or (output_dir / "below_median_scored.parquet")
    if not scored_path.is_file():
        alt = output_dir / "non_target_llm_scored.parquet"
        if alt.is_file():
            scored_path = alt
    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)

    full = pd.read_parquet(scored_path)
    disagree = full.loc[~full["agree_llm_logreg"]].copy()
    crosstab = (
        disagree.groupby(["llm_pred", "logreg_pred"], dropna=False)
        .agg(
            n=("id", "count"),
            mean_max_proba=("max_proba", "mean"),
            reject_rate=("logreg_pred_with_reject", lambda s: (s == "Non classifié").mean()),
        )
        .reset_index()
        .sort_values("n", ascending=False)
    )
    pairs_path = rep / "08_below_median_disagreement_pairs.csv"
    crosstab.to_csv(pairs_path, index=False)

    if full_unsampled:
        sample = disagree.sort_values("max_proba", ascending=False)
    else:
        sample = sample_disagreements_for_review(
            full,
            per_pair=per_pair,
            max_total=max_total,
            min_max_proba=min_max_proba,
            require_logreg_accept=require_logreg_accept,
        )

    if with_text and not sample.empty:
        logger.info("Fetching text and num_ej for %s review rows", len(sample))
        sample = _attach_review_context(sample)
    elif not sample.empty and "num_ej" not in sample.columns:
        ej_map = _ej_map_for_ids(sample["id"].astype(str).tolist())
        sample = sample.copy()
        sample["num_ej"] = sample["id"].astype(str).map(lambda i: ej_map.get(i, ""))

    for col in ("review_ok", "review_correct_label", "review_notes"):
        if col not in sample.columns:
            sample[col] = ""

    out_path = rep / (
        "08_below_median_disagreement_review_full.csv"
        if full_unsampled
        else "08_below_median_disagreement_review_sample.csv"
    )
    if "num_ej" in sample.columns:
        sample["num_ej"] = sample["num_ej"].fillna("").astype(str)
    cols = [c for c in REVIEW_COLUMNS if c in sample.columns]
    sample[cols].to_csv(out_path, index=False)
    logger.info("Wrote %s rows -> %s", len(sample), out_path)
    return out_path, pairs_path


def summarize_llm_error_reviews(review_csv: Path) -> dict[str, int | float | None]:
    """Après revue: combien de lignes marquées LLM faux (review_ok=non)."""
    df = pd.read_csv(review_csv)
    reviewed = df[df["review_ok"].astype(str).str.strip().str.lower().isin(("oui", "non", "yes", "no"))]
    if reviewed.empty:
        return {"reviewed": 0, "llm_wrong": 0, "llm_ok": 0, "llm_error_rate": None}
    llm_wrong = reviewed["review_ok"].astype(str).str.strip().str.lower().isin(("non", "no", "false", "0"))
    return {
        "reviewed": int(len(reviewed)),
        "llm_wrong": int(llm_wrong.sum()),
        "llm_ok": int((~llm_wrong).sum()),
        "llm_error_rate": float(llm_wrong.mean()),
    }