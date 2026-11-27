from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from docia.file_processing.processor.classify.artifacts import load_pipeline
from docia.file_processing.processor.classify.below_median import load_medians_by_class, load_thresholds
from docia.file_processing.processor.classify.constants import (
    CLASSIFIER_ARTIFACT_NAME,
    CONFUSION_PAIRS,
    DEFAULT_OUTPUT_DIR,
)
from docia.file_processing.processor.classify.disagreement_review import REVIEW_COLUMNS, _attach_review_context
from docia.file_processing.processor.classify.evaluate import accept_mask, apply_reject, predict_frame
from docia.file_processing.processor.classify.label_hierarchy import (
    HIERARCHY_REVISION,
    PRIORITY_COARSE_LABELS,
    TRAINABLE_COARSE,
    map_llm_to_coarse,
)

logger = logging.getLogger(__name__)

# Libellés fins LLM encore nommés CCP (parent coarse = AE / CCAP après hiérarchie f).
CCP_FINE_LLM_LABELS: frozenset[str] = frozenset({"ccp_simple", "ccp_vae", "ccap_vae"})


def _is_ccp_fine_llm(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().isin(CCP_FINE_LLM_LABELS)


SCORED_COLUMNS = [
    "id",
    "hash",
    "filename",
    "num_ej",
    "classification",
    "llm_pred",
    "llm_coarse",
    "label_train",
    "logreg_pred",
    "logreg_coarse",
    "logreg_pred_with_reject",
    "max_proba",
    "margin",
    "agree_llm_logreg",
    "agree_coarse",
    "ratio_extracted",
    "median_ratio_class",
    "nb_mot",
    "text_2000",
    "filename_normalized",
    "split",
]


def _coarse_for_logreg(pred: str | None) -> str | None:
    if pred is None or (isinstance(pred, float) and pd.isna(pred)):
        return None
    text = str(pred).strip()
    if not text:
        return None
    mapped = map_llm_to_coarse(text)
    if mapped is not None:
        return mapped
    if text in TRAINABLE_COARSE:
        return text
    return text


def _priority_score_coarse(row: pd.Series) -> float:
    prob = float(row.get("max_proba") or 0)
    margin = float(row.get("margin") or 0)
    rejected = row.get("logreg_pred_with_reject") == "Non classifié"
    boost = 0.0 if rejected else 0.05
    llm_c = str(row.get("llm_coarse") or "")
    lr_c = str(row.get("logreg_coarse") or "")
    pair = (llm_c, lr_c)
    if pair in CONFUSION_PAIRS or (pair[1], pair[0]) in CONFUSION_PAIRS:
        boost += 0.02
    if llm_c in PRIORITY_COARSE_LABELS or lr_c in PRIORITY_COARSE_LABELS:
        boost += 0.03
    return prob + 0.25 * margin + boost


def score_split_to_frame(
    output_dir: Path,
    split: str,
    *,
    parquet_path: Path | None = None,
    batch_size: int = 8_000,
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Score un split (train, calib, …) du parquet V2 et renvoie un DataFrame scored."""
    output_dir = output_dir.resolve()
    parquet_path = (parquet_path or (output_dir / "documents_raw.parquet")).resolve()
    if not parquet_path.is_file():
        raise FileNotFoundError(parquet_path)
    artifact = output_dir / CLASSIFIER_ARTIFACT_NAME
    if not artifact.is_file():
        raise FileNotFoundError(f"Missing classifier at {artifact}")

    medians = load_medians_by_class(output_dir)
    tau, margin = load_thresholds(output_dir)
    model = load_pipeline(output_dir)

    cols = [
        "id",
        "hash",
        "filename",
        "num_ej",
        "nb_mot",
        "text_2000",
        "filename_normalized",
        "classification",
        "label_train",
        "ratio_extracted",
        "split",
    ]
    parts: list[pd.DataFrame] = []
    scored_n = 0
    pf = pq.ParquetFile(parquet_path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=cols):
        chunk = batch.to_pandas()
        chunk = chunk.loc[chunk["split"].astype(str) == split].copy()
        if chunk.empty:
            continue
        chunk = chunk.loc[chunk["text_2000"].fillna("").astype(str).str.strip().astype(bool)]
        if max_rows is not None and scored_n >= max_rows:
            break
        if max_rows is not None and scored_n + len(chunk) > max_rows:
            chunk = chunk.iloc[: max_rows - scored_n]

        scored = predict_frame(model, chunk)
        scored["llm_pred"] = scored["classification"].astype(str)
        scored["llm_coarse"] = scored["classification"].map(map_llm_to_coarse)
        scored["logreg_pred"] = scored["pred"].astype(str)
        scored["logreg_coarse"] = scored["logreg_pred"].map(_coarse_for_logreg)
        scored["logreg_pred_with_reject"] = apply_reject(scored, tau, margin)
        scored["agree_llm_logreg"] = scored["llm_pred"] == scored["logreg_pred"]
        scored["agree_coarse"] = scored["llm_coarse"].astype(str) == scored["logreg_coarse"].astype(str)
        scored["median_ratio_class"] = pd.to_numeric(
            scored["classification"].map(lambda c: medians.get(str(c))),
            errors="coerce",
        )
        scored["num_ej"] = scored["num_ej"].fillna("").astype(str)
        scored["split"] = split

        slim = scored.loc[scored["llm_coarse"].notna()].copy()
        if slim.empty:
            continue
        slim = slim.drop(columns=["pred"], errors="ignore")
        keep = [c for c in SCORED_COLUMNS if c in slim.columns]
        parts.append(slim[keep])
        scored_n += len(slim)
        logger.info("%s scored batch: +%s (total=%s)", split, len(slim), scored_n)

    if not parts:
        raise RuntimeError(f"No rows scored for split={split!r}")
    return pd.concat(parts, ignore_index=True)


def score_train_split_from_parquet(
    output_dir: Path | None = None,
    *,
    parquet_path: Path | None = None,
    out_path: Path | None = None,
    batch_size: int = 8_000,
    max_rows: int | None = None,
) -> Path:
    """Score le split ``train`` du parquet V2 (offline) avec le joblib courant."""
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    out_path = (out_path or (output_dir / "train_scored.parquet")).resolve()
    if out_path.is_file():
        out_path.unlink()

    frame = score_split_to_frame(
        output_dir,
        "train",
        parquet_path=parquet_path,
        batch_size=batch_size,
        max_rows=max_rows,
    )
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), out_path)

    tau, margin = load_thresholds(output_dir)
    meta = output_dir / "reports" / "13_train_scoring_summary.md"
    meta.parent.mkdir(parents=True, exist_ok=True)
    disagree = frame.loc[~frame["agree_coarse"]]
    meta.write_text(
        f"# Train split scoring\n\n"
        f"hierarchy_revision: {HIERARCHY_REVISION}\n"
        f"tau={tau}, margin={margin}\n"
        f"scored: {len(frame)}\n"
        f"coarse_disagree: {len(disagree)} ({len(disagree)/len(frame):.4f})\n",
        encoding="utf-8",
    )
    return out_path


def _sample_coarse_disagreements(
    scored: pd.DataFrame,
    *,
    per_pair: int = 25,
    max_total: int = 800,
    min_max_proba: float = 0.85,
    require_logreg_accept: bool = False,
    priority_only: bool = False,
) -> pd.DataFrame:
    df = scored.loc[~scored["agree_coarse"]].copy()
    if priority_only:
        mask = df["llm_coarse"].astype(str).isin(PRIORITY_COARSE_LABELS) | df["logreg_coarse"].astype(
            str
        ).isin(PRIORITY_COARSE_LABELS)
        df = df.loc[mask]
    if require_logreg_accept:
        df = df.loc[df["logreg_pred_with_reject"] != "Non classifié"]
    df = df.loc[df["max_proba"] >= min_max_proba]
    if df.empty:
        return df
    df["_priority"] = df.apply(_priority_score_coarse, axis=1)
    parts: list[pd.DataFrame] = []
    for _, sub in df.groupby(["llm_coarse", "logreg_coarse"], dropna=False):
        parts.append(sub.sort_values("_priority", ascending=False).head(per_pair))
    sample = pd.concat(parts, ignore_index=True).sort_values("_priority", ascending=False)
    if len(sample) > max_total:
        sample = sample.head(max_total)
    return sample.drop(columns=["_priority"], errors="ignore")


def export_train_disagreement_review(
    output_dir: Path | None = None,
    *,
    scored_parquet: Path | None = None,
    per_pair: int = 25,
    max_total: int = 800,
    min_max_proba: float = 0.85,
    require_logreg_accept: bool = False,
    priority_only: bool = False,
    with_text: bool = True,
    refresh_text_from_db: bool = False,
) -> tuple[Path, Path]:
    """
    Échantillon de désaccords LLM (coarse) vs logreg sur le **train**, pour revue humaine.
    """
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    scored_path = scored_parquet or (output_dir / "train_scored.parquet")
    if not scored_path.is_file():
        scored_path = score_train_split_from_parquet(output_dir, out_path=scored_path)

    full = pd.read_parquet(scored_path)
    disagree = full.loc[~full["agree_coarse"]].copy()
    crosstab = (
        disagree.groupby(["llm_pred", "logreg_coarse"], dropna=False)
        .agg(
            n=("id", "count"),
            mean_max_proba=("max_proba", "mean"),
            reject_rate=("logreg_pred_with_reject", lambda s: (s == "Non classifié").mean()),
        )
        .reset_index()
        .sort_values("n", ascending=False)
    )
    pairs_path = rep / "13_train_disagreement_pairs.csv"
    crosstab.to_csv(pairs_path, index=False)

    coarse_crosstab = (
        disagree.groupby(["llm_coarse", "logreg_coarse"], dropna=False)
        .agg(n=("id", "count"), mean_max_proba=("max_proba", "mean"))
        .reset_index()
        .sort_values("n", ascending=False)
    )
    coarse_crosstab.to_csv(rep / "13_train_disagreement_pairs_coarse.csv", index=False)

    sample = _sample_coarse_disagreements(
        full,
        per_pair=per_pair,
        max_total=max_total,
        min_max_proba=min_max_proba,
        require_logreg_accept=require_logreg_accept,
        priority_only=priority_only,
    )
    if refresh_text_from_db and with_text and not sample.empty:
        sample = _attach_review_context(sample)
    elif with_text and not sample.empty and "text_2000" not in sample.columns:
        sample = _attach_review_context(sample)
    # text_2000 est déjà dans le parquet scored ; pas de fetch DB sauf --refresh-text-from-db

    extra = ("llm_coarse", "logreg_coarse")
    for col in ("review_ok", "review_correct_label", "review_notes"):
        if col not in sample.columns:
            sample[col] = ""

    out_path = rep / "13_train_disagreement_review_sample.csv"
    cols = list(dict.fromkeys([c for c in REVIEW_COLUMNS if c in sample.columns] + list(extra)))
    sample[cols].to_csv(out_path, index=False)

    summary = {
        "hierarchy_revision": HIERARCHY_REVISION,
        "scored_train_rows": len(full),
        "coarse_disagree": len(disagree),
        "review_sample_rows": len(sample),
        "per_pair": per_pair,
        "max_total": max_total,
        "min_max_proba": min_max_proba,
        "priority_only": priority_only,
    }
    (rep / "13_train_disagreement_review_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("Wrote train review sample %s rows -> %s", len(sample), out_path)
    return out_path, pairs_path


def _load_scored_splits_frames(
    output_dir: Path,
    *,
    scored_parquet: Path | None = None,
    rescore: bool = False,
    extra_splits: tuple[str, ...] = ("calib", "test"),
) -> pd.DataFrame:
    scored_path = scored_parquet or (output_dir / "train_scored.parquet")
    if rescore or not scored_path.is_file():
        score_train_split_from_parquet(output_dir, out_path=scored_path)
    train_scored = pd.read_parquet(scored_path)
    if "split" not in train_scored.columns:
        train_scored["split"] = "train"
    frames = [train_scored]
    for sp in extra_splits:
        if sp == "train":
            continue
        frames.append(score_split_to_frame(output_dir, sp))
    return pd.concat(frames, ignore_index=True)


def export_coarse_classes_below_threshold_review(
    output_dir: Path | None = None,
    *,
    coarse_classes: tuple[str, ...],
    scored_parquet: Path | None = None,
    rescore: bool = False,
    extra_splits: tuple[str, ...] = ("calib", "test"),
    review_csv_name: str = "15_train_ccap_below_threshold_review.csv",
    summary_json_name: str = "15_train_ccap_below_threshold_summary.json",
) -> tuple[Path, Path]:
    """
    Export exhaustif sous seuil prod pour plusieurs ``label_train`` coarse dans un seul CSV.
    """
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    tau, margin_th = load_thresholds(output_dir)
    full = _load_scored_splits_frames(
        output_dir,
        scored_parquet=scored_parquet,
        rescore=rescore,
        extra_splits=extra_splits,
    )

    below_parts: list[pd.DataFrame] = []
    by_class: dict[str, dict] = {}
    for coarse_class in coarse_classes:
        subset = full.loc[full["label_train"].astype(str).eq(coarse_class)].copy()
        if subset.empty:
            logger.warning("No rows for label_train=%s", coarse_class)
            continue
        accept = accept_mask(subset, tau, margin_th)
        below = subset.loc[~accept].copy()
        below["threshold_tau"] = tau
        below["threshold_margin"] = margin_th
        below["below_tau"] = below["max_proba"] < tau - 1e-12
        below["below_margin"] = below["margin"] < margin_th - 1e-12
        below["argmax_is_label"] = below["logreg_coarse"].astype(str) == coarse_class
        below_parts.append(below)

        by_split: dict[str, dict[str, float | int]] = {}
        for sp, sub in subset.groupby(subset["split"].astype(str), observed=True):
            bel = below.loc[below["split"].astype(str) == sp]
            by_split[sp] = {
                "label_rows": len(sub),
                "below_threshold_rows": len(bel),
                "below_threshold_frac": len(bel) / len(sub) if len(sub) else 0.0,
                "argmax_is_label_below": int(bel["argmax_is_label"].sum()) if len(bel) else 0,
            }
        by_class[coarse_class] = {
            "by_split": by_split,
            "below_threshold_rows": len(below),
            "argmax_is_label_below": int(below["argmax_is_label"].sum()) if len(below) else 0,
        }

    if not below_parts:
        raise RuntimeError(f"No below-threshold rows for coarse_classes={coarse_classes!r}")

    below = pd.concat(below_parts, ignore_index=True)
    for col in ("review_ok", "review_correct_label", "review_notes"):
        if col not in below.columns:
            below[col] = ""

    out_path = rep / review_csv_name
    extra = ("llm_coarse", "logreg_coarse", "label_train", "split", "threshold_tau", "threshold_margin")
    meta_cols = ("below_tau", "below_margin", "argmax_is_label")
    cols = list(
        dict.fromkeys(
            [c for c in REVIEW_COLUMNS if c in below.columns]
            + [c for c in extra if c in below.columns]
            + [c for c in meta_cols if c in below.columns]
        )
    )
    below = below.sort_values(
        ["label_train", "split", "max_proba", "margin"],
        ascending=[True, True, True, True],
    )
    below[cols].to_csv(out_path, index=False)

    summary = {
        "hierarchy_revision": HIERARCHY_REVISION,
        "coarse_classes": list(coarse_classes),
        "tau": tau,
        "margin": margin_th,
        "splits": ["train", *extra_splits],
        "by_class": by_class,
        "below_threshold_rows": len(below),
        "argmax_is_label_below": int(below["argmax_is_label"].sum()),
        "mean_max_proba_below": float(below["max_proba"].mean()) if len(below) else None,
        "classification_counts_below": below["classification"].astype(str).value_counts().head(30).to_dict(),
    }
    summary_path = rep / summary_json_name
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "Wrote %s below-threshold rows (%s) train+%s -> %s",
        len(below),
        ",".join(coarse_classes),
        "+".join(extra_splits) or "train-only",
        out_path,
    )
    return out_path, summary_path


def export_train_coarse_below_threshold_review(
    output_dir: Path | None = None,
    *,
    coarse_class: str,
    scored_parquet: Path | None = None,
    rescore: bool = False,
    extra_splits: tuple[str, ...] = ("calib", "test"),
) -> tuple[Path, Path]:
    slug = coarse_class.replace("/", "_")
    return export_coarse_classes_below_threshold_review(
        output_dir,
        coarse_classes=(coarse_class,),
        scored_parquet=scored_parquet,
        rescore=rescore,
        extra_splits=extra_splits,
        review_csv_name=f"15_train_{slug}_below_threshold_review.csv",
        summary_json_name=f"15_train_{slug}_below_threshold_summary.json",
    )


def _sample_priority_agreement_low_confidence(
    scored: pd.DataFrame,
    *,
    per_class: int = 40,
    max_total: int = 400,
    max_proba_ceiling: float = 0.92,
    min_max_proba: float = 0.55,
    exclude_ccp_fine: bool = False,
) -> pd.DataFrame:
    """Accords coarse sur classes prioritaires, logreg peu confiante (risque d'accord faux)."""
    df = scored.loc[scored["agree_coarse"]].copy()
    df = df.loc[df["llm_coarse"].astype(str).isin(PRIORITY_COARSE_LABELS)]
    df = df.loc[(df["max_proba"] >= min_max_proba) & (df["max_proba"] < max_proba_ceiling)]
    if exclude_ccp_fine:
        df = df.loc[~_is_ccp_fine_llm(df["llm_pred"])]
    if df.empty:
        return df
    # Les plus basses proba en premier = accords les plus fragiles
    df["_sort"] = df["max_proba"] + 0.1 * df["margin"].fillna(0)
    parts: list[pd.DataFrame] = []
    for _, sub in df.groupby("llm_coarse", dropna=False):
        parts.append(sub.sort_values("_sort", ascending=True).head(per_class))
    sample = pd.concat(parts, ignore_index=True).sort_values("_sort", ascending=True)
    if len(sample) > max_total:
        sample = sample.head(max_total)
    return sample.drop(columns=["_sort"], errors="ignore")


def export_train_priority_agreement_low_confidence_review(
    output_dir: Path | None = None,
    *,
    scored_parquet: Path | None = None,
    per_class: int = 40,
    max_total: int = 400,
    max_proba_ceiling: float = 0.92,
    min_max_proba: float = 0.55,
    exclude_ccp_fine: bool = False,
    with_text: bool = True,
    refresh_text_from_db: bool = False,
) -> tuple[Path, Path]:
    """
    Échantillon train : **accord** LLM/logreg (coarse) sur **PRIORITY_COARSE_LABELS**
    mais ``max_proba`` sous le plafond → revue des faux positifs communs.
    """
    output_dir = (output_dir or DEFAULT_OUTPUT_DIR).resolve()
    rep = output_dir / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    scored_path = scored_parquet or (output_dir / "train_scored.parquet")
    if not scored_path.is_file():
        scored_path = score_train_split_from_parquet(output_dir, out_path=scored_path)

    full = pd.read_parquet(scored_path)
    agree_pri = full.loc[
        full["agree_coarse"] & full["llm_coarse"].astype(str).isin(PRIORITY_COARSE_LABELS)
    ].copy()
    agree_pri["is_ccp_fine"] = _is_ccp_fine_llm(agree_pri["llm_pred"])
    pool_stats = (
        agree_pri.groupby("llm_coarse", dropna=False)
        .agg(
            n=("id", "count"),
            mean_max_proba=("max_proba", "mean"),
        )
        .reset_index()
    )
    pool_stats["below_ceiling"] = [
        int((agree_pri.loc[agree_pri["llm_coarse"] == c, "max_proba"] < max_proba_ceiling).sum())
        for c in pool_stats["llm_coarse"]
    ]
    pool_stats = pool_stats.sort_values("n", ascending=False)
    stats_path = rep / "14_train_priority_agreement_low_conf_stats.csv"
    pool_stats.to_csv(stats_path, index=False)

    out_suffix = "_no_ccp" if exclude_ccp_fine else ""
    sample = _sample_priority_agreement_low_confidence(
        full,
        per_class=per_class,
        max_total=max_total,
        max_proba_ceiling=max_proba_ceiling,
        min_max_proba=min_max_proba,
        exclude_ccp_fine=exclude_ccp_fine,
    )
    if refresh_text_from_db and with_text and not sample.empty:
        sample = _attach_review_context(sample)
    elif with_text and not sample.empty and "text_2000" not in sample.columns:
        sample = _attach_review_context(sample)

    for col in ("review_ok", "review_correct_label", "review_notes"):
        if col not in sample.columns:
            sample[col] = ""

    extra = ("llm_coarse", "logreg_coarse", "agree_coarse")
    out_path = rep / f"14_train_priority_agreement_low_conf_review_sample{out_suffix}.csv"
    cols = list(dict.fromkeys([c for c in REVIEW_COLUMNS if c in sample.columns] + list(extra)))
    sample[cols].to_csv(out_path, index=False)

    band = (agree_pri["max_proba"] >= min_max_proba) & (agree_pri["max_proba"] < max_proba_ceiling)
    pool_n = int(agree_pri.loc[band].shape[0])
    pool_ccp = int(agree_pri.loc[band & agree_pri["is_ccp_fine"]].shape[0])
    if exclude_ccp_fine:
        pool_n = int(agree_pri.loc[band & ~agree_pri["is_ccp_fine"]].shape[0])
    summary = {
        "hierarchy_revision": HIERARCHY_REVISION,
        "pool_priority_agree_low_conf": pool_n,
        "pool_ccp_fine_in_band": pool_ccp,
        "exclude_ccp_fine": exclude_ccp_fine,
        "review_sample_rows": len(sample),
        "per_class": per_class,
        "max_total": max_total,
        "max_proba_ceiling": max_proba_ceiling,
        "min_max_proba": min_max_proba,
    }
    (rep / f"14_train_priority_agreement_low_conf_review_summary{out_suffix}.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (rep / f"14_train_priority_agreement_low_conf_review_summary{out_suffix}.md").write_text(
        f"# Accord prioritaire faible confiance (train)\n\n"
        f"Critère: `agree_coarse` et `llm_coarse` ∈ priorité, "
        f"`{min_max_proba} <= max_proba < {max_proba_ceiling}`."
        f"{' Sans libellés fins CCP.' if exclude_ccp_fine else ''}\n\n"
        f"Pool: {pool_n} (dont CCP fin: {pool_ccp}) | Échantillon: {len(sample)} | "
        f"revision: {HIERARCHY_REVISION}\n\n"
        f"**Annotation** : `review_ok=oui` si l'accord est correct ; `non` si silver ET logreg se trompent "
        f"→ `review_correct_label` = parent coarse correct.\n",
        encoding="utf-8",
    )
    logger.info("Wrote priority low-conf agreement sample %s -> %s", len(sample), out_path)
    return out_path, stats_path