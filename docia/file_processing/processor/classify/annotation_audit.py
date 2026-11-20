from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.constants import (
    AUDIT_SAMPLE_PER_CLASS,
    CLASSES_RATIO_MEDIAN,
    CONFUSION_PAIRS,
    DEFAULT_SEED,
    KEYWORD_MISMATCH_WARN_RATIO,
    TARGET_CLASSES,
)


def _keyword_mismatch(row: pd.Series) -> bool:
    fn = (row.get("filename_normalized") or "").lower()
    head = (row.get("text_2000") or "").lower()
    label = row.get("classification")
    hints: dict[str, tuple[str, ...]] = {
        "devis": ("devis",),
        "bordereau_prix": ("bpu", "bordereau"),
        "detail_quantitatif_estimatif": ("dqe", "quantitatif"),
        "ccap": ("ccap",),
        "cctp": ("cctp",),
        "sous_traitance": ("sous traitance", "sous-traitance", "dc4"),
        "rib": ("rib", "iban"),
        "acte_engagement": ("acte", "engagement"),
    }
    for other, tokens in hints.items():
        if other == label:
            continue
        if any(t in fn or t in head[:500] for t in tokens):
            return True
    return False


def _confusable_flag(row: pd.Series) -> bool:
    label = row.get("classification")
    head = (row.get("filename_normalized") or "") + " " + (row.get("text_2000") or "")[:300]
    head = head.lower()
    for a, b in CONFUSION_PAIRS:
        if label == a:
            partner = b.replace("_", " ")
            if partner in head or b in head:
                return True
        if label == b:
            partner = a.replace("_", " ")
            if partner in head or a in head:
                return True
    return False


def build_heuristics(df: pd.DataFrame) -> pd.DataFrame:
    targets = df[df["classification"].isin(TARGET_CLASSES)].copy()
    flags = []
    for _, row in targets.iterrows():
        zero_fill = (
            bool(row.get("analyzed_at"))
            and row["classification"] in CLASSES_RATIO_MEDIAN
            and float(row.get("ratio_extracted") or 0) == 0.0
        )
        flags.append(
            {
                "id": row["id"],
                "classification": row["classification"],
                "keyword_mismatch": _keyword_mismatch(row),
                "confusable_neighbor": _confusable_flag(row),
                "zero_fill_in_median_class": zero_fill,
            }
        )
    return pd.DataFrame(flags)


def sample_audit(df: pd.DataFrame, seed: int = DEFAULT_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    targets = df[df["classification"].isin(TARGET_CLASSES)]
    rows = []
    heur = build_heuristics(targets).set_index("id")
    for cls in sorted(TARGET_CLASSES):
        pool = targets[targets["classification"] == cls]
        if pool.empty:
            continue
        risk_ids = set()
        if not heur.empty:
            sub = heur[heur.index.isin(pool["id"])]
            risk_ids = set(sub[(sub["keyword_mismatch"]) | (sub["confusable_neighbor"])].index.astype(str))
        risk = pool[pool["id"].astype(str).isin(risk_ids)]
        rest = pool[~pool["id"].astype(str).isin(risk_ids)]
        take_risk = min(len(risk), AUDIT_SAMPLE_PER_CLASS // 2)
        take_rand = min(AUDIT_SAMPLE_PER_CLASS - take_risk, len(rest))
        parts = []
        if take_risk:
            parts.append(risk.iloc[rng.choice(len(risk), size=take_risk, replace=False)])
        if take_rand:
            parts.append(rest.iloc[rng.choice(len(rest), size=take_rand, replace=False)])
        if parts:
            rows.append(pd.concat(parts))
    if not rows:
        return pd.DataFrame()
    audit = pd.concat(rows)
    audit = audit.copy()
    for col in ("review_ok", "review_correct_label", "review_notes"):
        audit[col] = ""
    return audit


def audit_summary(heuristics: pd.DataFrame) -> dict[str, float]:
    if heuristics.empty:
        return {}
    out = {}
    for cls, grp in heuristics.groupby("classification"):
        rate = grp["keyword_mismatch"].mean()
        out[str(cls)] = float(rate)
    return out


def write_audit_reports(df: pd.DataFrame, output_dir: Path, seed: int, strict: bool) -> list[str]:
    warnings: list[str] = []
    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    heur = build_heuristics(df[df["classification"].isin(TARGET_CLASSES)])
    heur.to_csv(rep / "01_annotation_heuristics.csv", index=False)
    audit = sample_audit(df, seed=seed)
    audit.to_csv(rep / "01_annotation_audit_sample.csv", index=False)
    summary_rates = audit_summary(heur)
    lines = ["# Annotation audit", ""]
    for cls, rate in summary_rates.items():
        lines.append(f"- {cls}: keyword_mismatch rate {rate:.1%}")
        if rate > KEYWORD_MISMATCH_WARN_RATIO:
            msg = f"Class {cls} keyword_mismatch rate {rate:.1%} > {KEYWORD_MISMATCH_WARN_RATIO:.0%}"
            warnings.append(msg)
            lines.append(f"  - WARNING: {msg}")
    (rep / "01_annotation_audit_summary.md").write_text("\n".join(lines), encoding="utf-8")
    if strict and warnings:
        raise RuntimeError("Strict audit failed:\n" + "\n".join(warnings))
    return warnings


def import_audit_results(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    reviewed = df[df["review_ok"].astype(str).str.lower().isin(("oui", "yes", "true", "1"))]
    if reviewed.empty:
        return {"reviewed": 0, "accuracy": None}
    correct = reviewed["classification"].astype(str) == reviewed["review_correct_label"].fillna(
        reviewed["classification"]
    ).astype(str)
    ok = reviewed["review_ok"].astype(str).str.lower().isin(("oui", "yes", "true", "1")) & (
        reviewed["review_correct_label"].fillna("").astype(str).eq("")
        | correct
    )
    return {"reviewed": int(len(reviewed)), "accuracy": float(ok.mean())}