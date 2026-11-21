from __future__ import annotations

import logging

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, log_loss

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.constants import DEFAULT_SEED
from docia.file_processing.processor.classify.features import build_model_pipeline
from docia.file_processing.processor.classify.label_hierarchy import (
    COARSE_ACTE_ENGAGEMENT,
    PRIORITY_CLASS_WEIGHT_FACTOR,
    PRIORITY_COARSE_LABELS,
)

logger = logging.getLogger(__name__)

C_GRID = [1e-3, 1e-2, 1e-1, 1, 10, 100]


def _class_weights(y: pd.Series, *, boost_priority: bool) -> dict[str, float] | str:
    if not boost_priority:
        return "balanced"
    labels = np.array(sorted(y.unique()))
    n_samples = len(y)
    n_classes = len(labels)
    weight_map: dict[str, float] = {}
    for label in labels:
        n_label = (y == label).sum()
        weight_map[str(label)] = float(n_samples / (n_classes * max(n_label, 1)))
    for label in PRIORITY_COARSE_LABELS:
        if label in weight_map:
            weight_map[label] *= PRIORITY_CLASS_WEIGHT_FACTOR
    return weight_map


def _features_labels(df: pd.DataFrame, label_col: str = "label_train"):
    sub = df[df[label_col].notna()].copy()
    x = sub[["text_2000", "filename_normalized", "nb_mot"]].copy()
    x["nb_mot"] = x["nb_mot"].fillna(0)
    y = sub[label_col].astype(str)
    return x, y


def baseline_majority(train_df: pd.DataFrame, val_df: pd.DataFrame, label_col: str = "label_train") -> dict:
    train_y = train_df[label_col].dropna().astype(str)
    if train_y.empty:
        return {"majority_log_loss": None, "majority_macro_f1": None}
    majority = train_y.mode().iloc[0]
    val_y = val_df[label_col].dropna().astype(str)
    pred = np.array([majority] * len(val_y))
    macro_f1 = f1_score(val_y, pred, average="macro", zero_division=0)
    return {"majority_class": majority, "majority_macro_f1": float(macro_f1)}


def baseline_filename_rule(val_df: pd.DataFrame, label_col: str = "label_train") -> dict:
    rules = [
        ("rib", "rib"),
        ("devis", "devis"),
        ("dqe", "detail_quantitatif_estimatif"),
        ("bpu", "bordereau_prix"),
        ("ccap", "ccap"),
        ("cctp", "cctp"),
        ("sous", "sous_traitance"),
    ]
    val_y = val_df[label_col].dropna().astype(str)
    preds = []
    for _, row in val_df.iterrows():
        fn = (row.get("filename_normalized") or "").lower()
        found = "unknown"
        for token, label in rules:
            if token in fn:
                found = label
                break
        preds.append(found)
    aligned = val_df[label_col].notna()
    macro_f1 = f1_score(val_y, np.array(preds)[aligned.values], average="macro", zero_division=0)
    return {"filename_rules_macro_f1": float(macro_f1)}


def stratified_train_sample(train_df: pd.DataFrame, n: int, seed: int = DEFAULT_SEED) -> pd.DataFrame:
    from docia.file_processing.processor.classify.corpus_profile.vocab_curve import nested_stratified_take

    train_y = train_df[train_df["label_train"].notna()]
    if len(train_y) <= n:
        return train_y
    sub = nested_stratified_take(train_y, n, seed)
    logger.info("Stratified train sample: %s -> %s rows", len(train_y), len(sub))
    return sub


def _label_seed(label: str, seed: int) -> int:
    return seed + (hash(label) % 10_000)


def _sample_group(grp: pd.DataFrame, n_take: int, label: str, seed: int) -> pd.DataFrame:
    if len(grp) <= n_take:
        return grp
    return grp.sample(n=n_take, random_state=_label_seed(label, seed))


def _default_priority_per_class_n(train_y: pd.DataFrame) -> int:
    """Référence : effectif train d'acte_engagement (équilibre devis = AE, etc.)."""
    ae = train_y[train_y["_label"] == COARSE_ACTE_ENGAGEMENT]
    if len(ae) > 0:
        return len(ae)
    sizes = [
        len(g)
        for lab, g in train_y.groupby("_label")
        if lab in PRIORITY_COARSE_LABELS
    ]
    return int(np.median(sizes)) if sizes else 5_000


def priority_undersample_train(
    train_df: pd.DataFrame,
    seed: int = DEFAULT_SEED,
    *,
    max_total: int | None = None,
    non_priority_cap: int | None = None,
    priority_per_class_n: int | None = None,
) -> pd.DataFrame:
    """Classes PRIORITY_COARSE_LABELS : au plus ``priority_per_class_n`` (défaut = effectif AE)."""
    train_y = train_df[train_df["label_train"].notna()].copy()
    train_y["_label"] = train_y["label_train"].astype(str)

    per_priority = priority_per_class_n
    if per_priority is None:
        per_priority = _default_priority_per_class_n(train_y)

    if non_priority_cap is None:
        non_priority_cap = per_priority

    priority_parts: list[pd.DataFrame] = []
    other_groups: list[tuple[str, pd.DataFrame]] = []
    for label, grp in train_y.groupby("_label", sort=True):
        if label in PRIORITY_COARSE_LABELS:
            priority_parts.append(_sample_group(grp, per_priority, label, seed))
        else:
            other_groups.append((label, grp))

    priority_df = pd.concat(priority_parts, ignore_index=True) if priority_parts else train_y.iloc[0:0]
    n_priority = len(priority_df)

    per_other = non_priority_cap
    if max_total is not None:
        if max_total <= n_priority:
            logger.warning("max_total=%s <= priority sample=%s: priority only", max_total, n_priority)
            out = priority_df.drop(columns=["_label"], errors="ignore")
            return out.head(max_total) if max_total < len(out) else out
        if other_groups:
            per_other = max(1, min(non_priority_cap, (max_total - n_priority) // len(other_groups)))

    other_parts = [
        _sample_group(grp, min(len(grp), per_other), label, seed) for label, grp in other_groups
    ]

    out = pd.concat([priority_df, *other_parts], ignore_index=True)
    out = out.drop(columns=["_label"], errors="ignore")
    counts_p = {lab: int((out["label_train"].astype(str) == lab).sum()) for lab in PRIORITY_COARSE_LABELS}
    logger.info(
        "Priority undersample train: %s -> %s (per_priority=%s cap_other=%s per_other~=%s)",
        len(train_y),
        len(out),
        per_priority,
        non_priority_cap,
        per_other,
    )
    logger.info("Priority counts: %s", counts_p)
    return out


def apply_train_sample(
    train_df: pd.DataFrame,
    *,
    mode: str,
    seed: int,
    max_total: int | None = None,
    non_priority_cap: int | None = None,
    priority_per_class_n: int | None = None,
) -> pd.DataFrame:
    if not max_total and mode != "priority_undersample":
        return train_df
    if mode == "priority_undersample":
        return priority_undersample_train(
            train_df,
            seed,
            max_total=max_total,
            non_priority_cap=non_priority_cap,
            priority_per_class_n=priority_per_class_n,
        )
    if max_total is None:
        return train_df
    return stratified_train_sample(train_df, max_total, seed=seed)


def grid_search_c(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    seed: int = DEFAULT_SEED,
    *,
    boost_priority_classes: bool = False,
    c_grid: list[float] | None = None,
) -> tuple[float, list[dict]]:
    x_train, y_train = _features_labels(train_df)
    x_val, y_val = _features_labels(val_df)

    grid = [float(x) for x in (c_grid if c_grid is not None else C_GRID)]
    rows = []
    best_c = grid[0]
    best_loss = float("inf")
    classes = sorted(y_train.unique())
    logger.info(
        "Grid search C: train=%s val=%s classes=%s grid=%s",
        len(y_train),
        len(y_val),
        len(classes),
        grid,
    )

    class_weight = _class_weights(y_train, boost_priority=boost_priority_classes)
    for i, c in enumerate(grid, start=1):
        logger.info("Grid %s/%s: fitting C=%s (TF-IDF + logistic saga)...", i, len(grid), c)
        clf = LogisticRegression(
            C=c,
            solver="saga",
            max_iter=2000,
            class_weight=class_weight,
            random_state=seed,
        )
        pipe = build_model_pipeline(clf)
        pipe.fit(x_train, y_train)
        proba_val = pipe.predict_proba(x_val)
        val_loss = log_loss(y_val, proba_val, labels=classes)
        val_f1 = f1_score(y_val, pipe.predict(x_val), average="macro", zero_division=0)
        proba_train = pipe.predict_proba(x_train)
        train_loss = log_loss(y_train, proba_train, labels=classes)
        train_f1 = f1_score(y_train, pipe.predict(x_train), average="macro", zero_division=0)
        gap_loss = train_loss - val_loss
        gap_f1 = train_f1 - val_f1
        rows.append(
            {
                "C": c,
                "train_log_loss": train_loss,
                "val_log_loss": val_loss,
                "log_loss": val_loss,
                "train_macro_f1": train_f1,
                "val_macro_f1": val_f1,
                "macro_f1": val_f1,
                "overfit_loss_gap": gap_loss,
                "overfit_f1_gap": gap_f1,
            }
        )
        logger.info(
            "Grid C=%s: train loss=%.4f f1=%.4f | val loss=%.4f f1=%.4f | gap_f1=%+.4f%s",
            c,
            train_loss,
            train_f1,
            val_loss,
            val_f1,
            gap_f1,
            " (best val loss)" if val_loss < best_loss else "",
        )
        if val_loss < best_loss:
            best_loss = val_loss
            best_c = c
    logger.info("Grid search done: best_C=%s val_log_loss=%.4f", best_c, best_loss)
    return best_c, rows


def fit_classifier(
    train_df: pd.DataFrame,
    c: float,
    seed: int = DEFAULT_SEED,
    *,
    boost_priority_classes: bool = False,
):
    x, y = _features_labels(train_df)
    logger.info("Final fit on full train split: n=%s C=%s", len(y), c)
    clf = LogisticRegression(
        C=c,
        solver="saga",
        max_iter=3000,
        class_weight=_class_weights(y, boost_priority=boost_priority_classes),
        random_state=seed,
    )
    pipe = build_model_pipeline(clf)
    pipe.fit(x, y)
    logger.info("Final fit complete (%s classes)", len(y.unique()))
    return pipe, sorted(y.unique())