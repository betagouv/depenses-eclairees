from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from docia.file_processing.processor.classify.constants import (
    CORE_FOUR_MISSED_TRACKING,
    DEFAULT_OUTPUT_DIR,
    TARGET_CLASSES,
)
from docia.file_processing.processor.classify.disagreement_review import REVIEW_COLUMNS, _attach_review_context

logger = logging.getLogger(__name__)

OTHER_TARGET_CLASSES = TARGET_CLASSES - CORE_FOUR_MISSED_TRACKING


def flag_llm_missed_core_four(df: pd.DataFrame) -> pd.DataFrame:
    """LLM hors {AE, CCAP, ST, RIB} mais logreg accepte l'une de ces classes."""
    out = df.copy()
    llm = out["llm_pred"].astype(str)
    logreg = out["logreg_pred"].astype(str)
    accepted = out["logreg_pred_with_reject"].astype(str) != "Non classifié"
    out["llm_in_core_four"] = llm.isin(CORE_FOUR_MISSED_TRACKING)
    out["logreg_in_core_four"] = logreg.isin(CORE_FOUR_MISSED_TRACKING)
    out["llm_missed_core_four"] = ~out["llm_in_core_four"] & out["logreg_in_core_four"] & accepted
    return out


def _load_scored_slices(output_dir: Path) -> pd.DataFrame:
    paths = [
        output_dir / "non_target_llm_scored.parquet",
        output_dir / "below_median_scored.parquet",
        output_dir / "other_target_llm_scored.parquet",
    ]
    parts: list[pd.DataFrame] = []
    for p in paths:
        if not p.is_file():
            logger.warning("Missing scored parquet: %s", p)
            continue
        parts.append(pd.read_parquet(p))
    if not parts:
        raise FileNotFoundError("No scored parquet found for core-four tracking")
    merged = pd.concat(parts, ignore_index=True)
    merged = merged.drop_duplicates(subset=["id"], keep="first")
    return flag_llm_missed_core_four(merged)


def build_core_four_reports(output_dir: Path | None = None) -> tuple[Path, Path, int]:
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)

    full = _load_scored_slices(output_dir)
    pool = full.loc[full["llm_missed_core_four"]].copy()
    pool = pool.sort_values("max_proba", ascending=False)
    pool.to_csv(rep / "10_llm_missed_core_four.csv", index=False)

    summary_rows = []
    for cls, sub in full.groupby("classification", dropna=False):
        n = len(sub)
        summary_rows.append(
            {
                "llm_classification": cls,
                "n_scored": n,
                "llm_missed_core_four_count": int(sub["llm_missed_core_four"].sum()),
                "llm_missed_core_four_rate": round(float(sub["llm_missed_core_four"].mean()), 4) if n else 0.0,
                "mean_max_proba_when_flagged": (
                    round(float(sub.loc[sub["llm_missed_core_four"], "max_proba"].mean()), 4)
                    if sub["llm_missed_core_four"].any()
                    else None
                ),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values("llm_missed_core_four_count", ascending=False)
    summary_path = rep / "10_core_four_miss_summary.csv"
    summary.to_csv(summary_path, index=False)

    pair_rows = []
    if not pool.empty:
        for (llm, lr), sub in pool.groupby(["llm_pred", "logreg_pred"], dropna=False):
            pair_rows.append({"llm_pred": llm, "logreg_pred": lr, "n": len(sub), "mean_max_proba": sub["max_proba"].mean()})
        pd.DataFrame(pair_rows).sort_values("n", ascending=False).to_csv(rep / "10_core_four_miss_pairs.csv", index=False)

    (rep / "10_core_four_miss_summary.md").write_text(
        f"# Oublis LLM — acte_engagement / ccap / sous_traitance / rib\n\n"
        f"Documents scorés (union cohorts): {len(full)}\n"
        f"Candidats oubli (logreg accepte): {len(pool)}\n",
        encoding="utf-8",
    )
    logger.info("Core-four misses: %s / %s scored", len(pool), len(full))
    return summary_path, rep / "10_llm_missed_core_four.csv", len(pool)


def summarize_core_four_review(review_csv: Path, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = (output_dir or review_csv.parent).resolve()
    if review_csv.parent.name == "reports" and (review_csv.parent.parent / "dataset_manifest.json").exists():
        output_dir = review_csv.parent.parent
    df = pd.read_csv(review_csv)
    reviewed = df[df["review_ok"].astype(str).str.strip().str.lower().isin(("oui", "non", "yes", "no"))]
    llm_wrong = reviewed["review_ok"].astype(str).str.strip().str.lower().isin(("non", "no", "false", "0"))
    stats: dict[str, Any] = {
        "rows_in_csv": len(df),
        "reviewed": int(len(reviewed)),
        "pending": int(len(df) - len(reviewed)),
        "llm_wrong": int(llm_wrong.sum()),
        "logreg_false_positive_core_four": int((~llm_wrong).sum()),
    }
    if reviewed.empty:
        return stats

    correct = reviewed.loc[llm_wrong, "review_correct_label"].fillna("").astype(str).str.strip()
    confirmed = reviewed.loc[llm_wrong].copy()
    confirmed["review_correct_label"] = correct
    confirmed = confirmed[correct.isin(CORE_FOUR_MISSED_TRACKING)]

    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    confirmed.to_csv(rep / "10_core_four_confirmed_llm_omissions.csv", index=False)

    wrong_not_core = reviewed.loc[llm_wrong].copy()
    wrong_not_core["review_correct_label"] = correct
    wrong_not_core = wrong_not_core[~wrong_not_core["review_correct_label"].isin(CORE_FOUR_MISSED_TRACKING)]
    wrong_not_core.to_csv(rep / "10_core_four_logreg_false_positives_reviewed.csv", index=False)

    reviewed.loc[llm_wrong, "verdict"] = "llm_wrong"
    reviewed.loc[~llm_wrong, "verdict"] = "logreg_wrong_on_core_four"
    reviewed.to_csv(rep / "10_core_four_review_annotated.csv", index=False)

    stats["confirmed_core_four_omissions"] = int(len(confirmed))
    stats["llm_wrong_but_not_core_four"] = int(len(wrong_not_core))
    stats["confirmed_omission_rate"] = (
        round(len(confirmed) / len(reviewed), 4) if len(reviewed) else None
    )
    stats["logreg_fp_rate_in_reviewed"] = round((~llm_wrong).mean(), 4)

    (rep / "10_core_four_review_summary.md").write_text(
        "# Revue core-four (échantillon annoté)\n\n"
        f"- Lignes CSV: {stats['rows_in_csv']}\n"
        f"- Revues: {stats['reviewed']} (reste {stats['pending']})\n"
        f"- `review_ok=non` (silver faux): {stats['llm_wrong']}\n"
        f"- `review_ok=oui` (logreg trop agressive sur AE/CCAP/ST/RIB): "
        f"{stats['logreg_false_positive_core_four']}\n"
        f"- **Oublis LLM confirmés** (vraie classe ∈ core-four): "
        f"{stats['confirmed_core_four_omissions']}\n"
        f"- Faux signaux logreg (silver faux mais vraie classe hors core-four): "
        f"{stats['llm_wrong_but_not_core_four']}\n",
        encoding="utf-8",
    )
    pd.DataFrame([stats]).to_csv(rep / "10_core_four_review_summary.csv", index=False)
    return stats


def export_core_four_review_sample(
    output_dir: Path | None = None,
    *,
    per_pair: int = 15,
    max_total: int = 400,
    min_max_proba: float = 0.85,
    with_text: bool = True,
) -> Path:
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    candidates_path = output_dir / "reports" / "10_llm_missed_core_four.csv"
    if not candidates_path.is_file():
        build_core_four_reports(output_dir)
    pool = pd.read_csv(candidates_path)
    pool = pool[pool["max_proba"] >= min_max_proba]
    if pool.empty:
        raise RuntimeError("No core-four miss candidates above min_max_proba")

    pool["_priority"] = pool["max_proba"] + 0.25 * pool["margin"]
    parts: list[pd.DataFrame] = []
    for _, sub in pool.groupby(["llm_pred", "logreg_pred"], dropna=False):
        parts.append(sub.sort_values("_priority", ascending=False).head(per_pair))
    sample = pd.concat(parts, ignore_index=True).sort_values("_priority", ascending=False)
    if len(sample) > max_total:
        sample = sample.head(max_total)
    sample = sample.drop(columns=["_priority"], errors="ignore")

    if with_text:
        logger.info("Fetching text + num_ej for %s review rows", len(sample))
        sample = _attach_review_context(sample)

    for col in ("review_ok", "review_correct_label", "review_notes"):
        if col not in sample.columns:
            sample[col] = ""
    if "num_ej" in sample.columns:
        sample["num_ej"] = sample["num_ej"].fillna("").astype(str)

    out_path = output_dir / "reports" / "10_core_four_miss_review_sample.csv"
    cols = [c for c in REVIEW_COLUMNS if c in sample.columns]
    extra = [c for c in ("logreg_pred", "max_proba", "margin", "scoring_cohort") if c in sample.columns]
    sample[[*cols, *extra]].to_csv(out_path, index=False)
    return out_path