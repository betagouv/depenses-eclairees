from __future__ import annotations

from sklearn.metrics import classification_report, confusion_matrix, f1_score

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.artifacts import save_thresholds


def _features(df: pd.DataFrame) -> pd.DataFrame:
    x = df[["text_2000", "filename_normalized", "nb_mot"]].copy()
    x["nb_mot"] = x["nb_mot"].fillna(0)
    return x


def predict_frame(model, df: pd.DataFrame) -> pd.DataFrame:
    x = _features(df)
    proba = model.predict_proba(x)
    classes = list(model.classes_) if hasattr(model, "classes_") else list(model.estimator.classes_)
    out = df.copy()
    for i, c in enumerate(classes):
        out[f"p_{c}"] = proba[:, i]
    out["pred"] = model.predict(x)
    order = np.argsort(-proba, axis=1)
    out["max_proba"] = proba[np.arange(len(proba)), order[:, 0]]
    if proba.shape[1] > 1:
        out["margin"] = proba[np.arange(len(proba)), order[:, 0]] - proba[np.arange(len(proba)), order[:, 1]]
    else:
        out["margin"] = proba[:, 0]
    return out


def choose_thresholds(calib_df: pd.DataFrame, model) -> tuple[float, float]:
    scored = predict_frame(model, calib_df)
    targets = scored[scored["label_train"].notna()]
    rejections = scored[scored["label_train"].isna()]

    best_tau, best_margin = 0.5, 0.05
    best_score = -1.0
    for tau in np.linspace(0.2, 0.95, 16):
        for margin in np.linspace(0.0, 0.3, 7):
            accept = (targets["max_proba"] >= tau) & (targets["margin"] >= margin)
            if accept.sum() == 0:
                continue
            acc = (targets.loc[accept, "pred"] == targets.loc[accept, "label_train"]).mean()
            false_accept = 0.0
            if len(rejections):
                false_accept = ((rejections["max_proba"] >= tau) & (rejections["margin"] >= margin)).mean()
            score = acc - false_accept
            if score > best_score:
                best_score = score
                best_tau, best_margin = float(tau), float(margin)
    return best_tau, best_margin


def apply_reject(pred_df: pd.DataFrame, tau: float, margin: float) -> pd.Series:
    accept = (pred_df["max_proba"] >= tau) & (pred_df["margin"] >= margin)
    out = pred_df["pred"].astype(object)
    out[~accept] = "Non classifié"
    return out


def evaluate_test(test_df: pd.DataFrame, model, tau: float, margin: float) -> tuple[dict, pd.DataFrame]:
    scored = predict_frame(model, test_df)
    scored["pred_with_reject"] = apply_reject(scored, tau, margin)
    labeled = scored[scored["label_train"].notna()].copy()
    y_true = labeled["label_train"].astype(str)
    y_pred = labeled["pred"].astype(str)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    report = classification_report(y_true, y_pred, zero_division=0, output_dict=True)
    cm = confusion_matrix(y_true, y_pred, labels=sorted(y_true.unique()))
    cm_df = pd.DataFrame(cm, index=sorted(y_true.unique()), columns=sorted(y_true.unique()))
    metrics = {"macro_f1": float(macro_f1), "classification_report": report}
    return metrics, cm_df


def rejection_curve_rows(calib_df: pd.DataFrame, model) -> list[dict]:
    scored = predict_frame(model, calib_df)
    rows = []
    for tau in np.linspace(0.2, 0.95, 16):
        for margin in np.linspace(0.0, 0.3, 7):
            t = scored[scored["label_train"].notna()]
            r = scored[scored["label_train"].isna()]
            t_acc = ((t["max_proba"] >= tau) & (t["margin"] >= margin)).mean()
            r_fa = ((r["max_proba"] >= tau) & (r["margin"] >= margin)).mean() if len(r) else 0.0
            rows.append({"tau": tau, "margin": margin, "target_accept_rate": t_acc, "rejection_false_accept": r_fa})
    return rows


def save_evaluation_artifacts(output_dir, tau, margin, metrics, cm_df, rejection_rows):
    save_thresholds(output_dir, tau, margin)
    return metrics, cm_df, rejection_rows