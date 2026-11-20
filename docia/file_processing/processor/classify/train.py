from __future__ import annotations

import logging

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, log_loss

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.constants import DEFAULT_SEED
from docia.file_processing.processor.classify.features import build_model_pipeline

logger = logging.getLogger(__name__)

C_GRID = [1e-3, 1e-2, 1e-1, 1, 10, 100]


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


def grid_search_c(train_df: pd.DataFrame, val_df: pd.DataFrame, seed: int = DEFAULT_SEED) -> tuple[float, list[dict]]:
    x_train, y_train = _features_labels(train_df)
    x_val, y_val = _features_labels(val_df)

    rows = []
    best_c = C_GRID[0]
    best_loss = float("inf")
    classes = sorted(y_train.unique())
    logger.info(
        "Grid search C: train=%s val=%s classes=%s grid=%s",
        len(y_train),
        len(y_val),
        len(classes),
        C_GRID,
    )

    for i, c in enumerate(C_GRID, start=1):
        logger.info("Grid %s/%s: fitting C=%s (TF-IDF + logistic saga)...", i, len(C_GRID), c)
        clf = LogisticRegression(
            C=c,
            solver="saga",
            max_iter=2000,
            class_weight="balanced",
            random_state=seed,
        )
        pipe = build_model_pipeline(clf)
        pipe.fit(x_train, y_train)
        proba = pipe.predict_proba(x_val)
        loss = log_loss(y_val, proba, labels=classes)
        pred = pipe.predict(x_val)
        macro_f1 = f1_score(y_val, pred, average="macro", zero_division=0)
        rows.append({"C": c, "log_loss": loss, "macro_f1": macro_f1})
        logger.info("Grid C=%s: val log_loss=%.4f macro_f1=%.4f%s", c, loss, macro_f1, " (best)" if loss < best_loss else "")
        if loss < best_loss:
            best_loss = loss
            best_c = c
    logger.info("Grid search done: best_C=%s val_log_loss=%.4f", best_c, best_loss)
    return best_c, rows


def fit_classifier(train_df: pd.DataFrame, c: float, seed: int = DEFAULT_SEED):
    x, y = _features_labels(train_df)
    logger.info("Final fit on full train split: n=%s C=%s", len(y), c)
    clf = LogisticRegression(
        C=c,
        solver="saga",
        max_iter=3000,
        class_weight="balanced",
        random_state=seed,
    )
    pipe = build_model_pipeline(clf)
    pipe.fit(x, y)
    logger.info("Final fit complete (%s classes)", len(y.unique()))
    return pipe, sorted(y.unique())