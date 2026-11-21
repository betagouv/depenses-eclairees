from __future__ import annotations

from dataclasses import dataclass

from sklearn.metrics import classification_report, confusion_matrix, f1_score, roc_auc_score
from sklearn.preprocessing import label_binarize

import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.artifacts import save_thresholds
from docia.file_processing.processor.classify.constants import (
    DEFAULT_MAX_LLM_FALLBACK_RATE,
    DEFAULT_MIN_ROUTING_F1,
)
from docia.file_processing.processor.classify.label_hierarchy import COARSE_ACTE_ENGAGEMENT, PRIORITY_COARSE_LABELS

ROUTING_REJECT_LABEL = "Non classifié"

THRESHOLD_GRID_TAU = np.linspace(0.2, 0.95, 16)
THRESHOLD_GRID_MARGIN = np.linspace(0.0, 0.3, 7)


@dataclass(frozen=True, slots=True)
class ThresholdChoice:
    tau: float
    margin: float
    score: float
    routing: dict[str, float]
    constraint_met: bool
    max_llm_fallback_rate: float | None


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


def priority_capture_rate(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    priority_labels: frozenset[str] | None = None,
) -> float:
    """
    Part des docs prioritaires correctement classés ET acceptés (rejet = oubli).
    """
    priority = priority_labels or PRIORITY_COARSE_LABELS
    pri = scored[scored["label_train"].astype(str).isin(priority)]
    if pri.empty:
        return 0.0
    accept = (pri["max_proba"] >= tau) & (pri["margin"] >= margin)
    correct = pri["pred"].astype(str) == pri["label_train"].astype(str)
    return float((accept & correct).sum() / len(pri))


def class_routing_recall(
    scored: pd.DataFrame,
    class_name: str,
    tau: float,
    margin: float,
    *,
    label_col: str = "label_train",
) -> float:
    """
    Rappel prod d'une classe : sur ``pred_with_reject``, rejet ou mauvais libellé = FN.
    Même définition que ``classification_report[classe]['recall']`` en mode routage.
    """
    sub = scored[scored[label_col].notna() & (scored[label_col].astype(str) == class_name)]
    if sub.empty:
        return 0.0
    routed = apply_reject(sub, tau, margin)
    return float((routed.astype(str) == class_name).mean())


def routing_recall_by_class(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    label_col: str = "label_train",
) -> dict[str, float]:
    """Rappel prod pour chaque classe présente (rejet = miss)."""
    labeled = scored[scored[label_col].notna()]
    if labeled.empty:
        return {}
    classes = sorted(labeled[label_col].astype(str).unique())
    return {cls: class_routing_recall(scored, cls, tau, margin, label_col=label_col) for cls in classes}


def min_routing_recall(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    label_col: str = "label_train",
) -> float:
    per = routing_recall_by_class(scored, tau, margin, label_col=label_col)
    return float(min(per.values())) if per else 0.0


def _labeled_routed_series(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    label_col: str = "label_train",
) -> tuple[pd.Series, pd.Series] | tuple[None, None]:
    labeled = scored[scored[label_col].notna()].copy()
    if labeled.empty:
        return None, None
    y_true = labeled[label_col].astype(str)
    y_pred = apply_reject(labeled, tau, margin).astype(str)
    return y_true, y_pred


def routing_macro_f1(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    label_col: str = "label_train",
) -> float:
    """Macro-F1 prod (``pred_with_reject``, rejet = erreur). KPI principal seuils / eval."""
    y_true, y_pred = _labeled_routed_series(scored, tau, margin, label_col=label_col)
    if y_true is None:
        return 0.0
    labels = sorted(set(y_true.unique()) | set(y_pred.unique()))
    return float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))


def routing_f1_by_class(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    label_col: str = "label_train",
) -> dict[str, float]:
    y_true, y_pred = _labeled_routed_series(scored, tau, margin, label_col=label_col)
    if y_true is None:
        return {}
    labels = sorted(y_true.unique())
    report = classification_report(y_true, y_pred, labels=labels, zero_division=0, output_dict=True)
    return {cls: float(report[cls]["f1-score"]) for cls in labels if cls in report}


def min_routing_f1(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    label_col: str = "label_train",
) -> float:
    per = routing_f1_by_class(scored, tau, margin, label_col=label_col)
    return float(min(per.values())) if per else 0.0


def priority_routing_macro_f1(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    priority_labels: frozenset[str] | None = None,
    label_col: str = "label_train",
) -> float:
    priority = priority_labels or PRIORITY_COARSE_LABELS
    y_true, y_pred = _labeled_routed_series(scored, tau, margin, label_col=label_col)
    if y_true is None:
        return 0.0
    mask = y_true.isin(priority)
    if not mask.any():
        return 0.0
    yt, yp = y_true[mask], y_pred[mask]
    labels = sorted(set(yt.unique()) | set(yp.unique()))
    return float(f1_score(yt, yp, labels=labels, average="macro", zero_division=0))


def prob_auc_metrics(
    scored: pd.DataFrame,
    model,
    *,
    label_col: str = "label_train",
) -> dict[str, float]:
    """
    AUC OvR sur les probas calibrées — **indépendant des seuils**.
    Utile pour juger la séparation du modèle, pas le routage prod (tau/margin).
    """
    labeled = scored[scored[label_col].notna()].copy()
    if labeled.empty:
        return {}
    classes = list(model.classes_) if hasattr(model, "classes_") else list(model.estimator.classes_)
    prob_cols = [f"p_{c}" for c in classes]
    missing = [c for c in prob_cols if c not in labeled.columns]
    if missing:
        return {}
    y = labeled[label_col].astype(str)
    present = sorted(set(y.unique()) & {str(c) for c in classes})
    if len(present) < 2:
        return {}
    col_idx = {str(c): i for i, c in enumerate(classes)}
    proba = labeled[prob_cols].to_numpy(dtype=float)
    proba_present = np.column_stack([proba[:, col_idx[c]] for c in present])
    y_ovr = label_binarize(y, classes=present)
    if y_ovr.shape[1] == 1:
        y_ovr = np.hstack([1 - y_ovr, y_ovr])
    out: dict[str, float] = {
        "auc_macro_ovr": float(
            roc_auc_score(y_ovr, proba_present, multi_class="ovr", average="macro")
        )
    }
    if COARSE_ACTE_ENGAGEMENT in present:
        y_bin = (y == COARSE_ACTE_ENGAGEMENT).astype(int).to_numpy()
        ae_scores = proba[:, col_idx[COARSE_ACTE_ENGAGEMENT]].ravel()
        out["auc_acte_engagement"] = float(roc_auc_score(y_bin, ae_scores))
    return out


def priority_metrics(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    priority_labels: frozenset[str] | None = None,
) -> dict[str, float]:
    """F1 macro + F1 par classe prioritaire (routage prod)."""
    priority = priority_labels or PRIORITY_COARSE_LABELS
    pri = scored[scored["label_train"].notna() & scored["label_train"].astype(str).isin(priority)].copy()
    if pri.empty:
        return {"priority_macro_f1": 0.0, "priority_capture_rate": 0.0, "priority_min_class_f1": 0.0}
    all_f1 = routing_f1_by_class(scored, tau, margin)
    pri_f1 = {k: v for k, v in all_f1.items() if k in priority}
    routed = apply_reject(pri, tau, margin)
    correct_routed = routed.astype(str) == pri["label_train"].astype(str)
    return {
        "priority_macro_f1": priority_routing_macro_f1(scored, tau, margin, priority_labels=priority),
        "priority_capture_rate": float(correct_routed.mean()),
        "priority_min_class_f1": float(min(pri_f1.values())) if pri_f1 else 0.0,
        **{f"priority_f1_{k}": float(v) for k, v in pri_f1.items()},
    }


def _threshold_objective(
    scored: pd.DataFrame,
    targets: pd.DataFrame,
    rejections: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    optimize_priority: bool,
    priority_labels: frozenset[str] | None,
) -> float | None:
    false_accept = 0.0
    if len(rejections):
        false_accept = ((rejections["max_proba"] >= tau) & (rejections["margin"] >= margin)).mean()
    f1 = routing_macro_f1(scored, tau, margin)
    if not scored["label_train"].notna().any():
        return None
    if optimize_priority:
        f1_pri = priority_routing_macro_f1(scored, tau, margin, priority_labels=priority_labels)
        return 0.65 * f1 + 0.35 * f1_pri - false_accept
    return float(f1 - false_accept)


def choose_thresholds(
    calib_df: pd.DataFrame,
    model,
    *,
    optimize_priority: bool = False,
    priority_labels: frozenset[str] | None = None,
    max_llm_fallback_rate: float | None = DEFAULT_MAX_LLM_FALLBACK_RATE,
    min_routing_f1: float | None = DEFAULT_MIN_ROUTING_F1,
) -> ThresholdChoice:
    """
    Choisit (tau, margin) sur le split calib.

    Si ``max_llm_fallback_rate`` est défini, ne retient que les couples dont le
    routage sur **tout** le calib respecte le plafond LLM ; sinon minimise le
    fallback puis l'objectif classique.
    """
    scored = predict_frame(model, calib_df)
    targets = scored[scored["label_train"].notna()]
    rejections = scored[scored["label_train"].isna()]

    candidates: list[tuple[float, float, float, dict[str, float]]] = []
    for tau in THRESHOLD_GRID_TAU:
        for margin in THRESHOLD_GRID_MARGIN:
            score = _threshold_objective(
                scored,
                targets,
                rejections,
                float(tau),
                float(margin),
                optimize_priority=optimize_priority,
                priority_labels=priority_labels,
            )
            if score is None:
                continue
            routing = routing_metrics(
                scored,
                float(tau),
                float(margin),
                include_priority=False,
            )
            per_f1 = routing_f1_by_class(scored, float(tau), float(margin))
            routing["routing_macro_f1"] = routing_macro_f1(scored, float(tau), float(margin))
            routing["min_routing_f1"] = float(min(per_f1.values())) if per_f1 else 0.0
            if (
                min_routing_f1 is not None
                and per_f1
                and routing["min_routing_f1"] < min_routing_f1 - 1e-9
            ):
                continue
            candidates.append((float(score), float(tau), float(margin), routing))

    if not candidates:
        routing = routing_metrics(scored, 0.5, 0.05, include_priority=False)
        return ThresholdChoice(
            tau=0.5,
            margin=0.05,
            score=-1.0,
            routing=routing,
            constraint_met=False,
            max_llm_fallback_rate=max_llm_fallback_rate,
        )

    def _pick(pool: list[tuple[float, float, float, dict[str, float]]]) -> tuple[float, float, float, dict[str, float]]:
        return max(pool, key=lambda c: (c[0], -c[3]["llm_fallback_rate"]))

    if max_llm_fallback_rate is not None:
        feasible = [c for c in candidates if c[3]["llm_fallback_rate"] <= max_llm_fallback_rate + 1e-9]
        if feasible:
            score, tau, margin, routing = _pick(feasible)
            return ThresholdChoice(
                tau=tau,
                margin=margin,
                score=score,
                routing=routing,
                constraint_met=True,
                max_llm_fallback_rate=max_llm_fallback_rate,
            )
        # Aucun couple dans la grille : minimiser le fallback, puis objectif
        score, tau, margin, routing = min(candidates, key=lambda c: (c[3]["llm_fallback_rate"], -c[0]))
        return ThresholdChoice(
            tau=tau,
            margin=margin,
            score=score,
            routing=routing,
            constraint_met=False,
            max_llm_fallback_rate=max_llm_fallback_rate,
        )

    score, tau, margin, routing = _pick(candidates)
    return ThresholdChoice(
        tau=tau,
        margin=margin,
        score=score,
        routing=routing,
        constraint_met=True,
        max_llm_fallback_rate=None,
    )


def apply_reject(pred_df: pd.DataFrame, tau: float, margin: float) -> pd.Series:
    accept = (pred_df["max_proba"] >= tau) & (pred_df["margin"] >= margin)
    out = pred_df["pred"].astype(object)
    out[~accept] = ROUTING_REJECT_LABEL
    return out


def accept_mask(scored: pd.DataFrame, tau: float, margin: float) -> pd.Series:
    return (scored["max_proba"] >= tau) & (scored["margin"] >= margin)


def routing_metrics(
    scored: pd.DataFrame,
    tau: float,
    margin: float,
    *,
    include_priority: bool = True,
    priority_labels: frozenset[str] | None = None,
) -> dict[str, float]:
    """
    Routage prod : part des docs envoyés au LLM (rejet) vs logreg.
    Ne pas confondre avec la qualité du classifieur (voir macro_f1 sur ``pred``).
    """
    accept = accept_mask(scored, tau, margin)
    n = len(scored)
    out: dict[str, float] = {
        "tau": float(tau),
        "margin": float(margin),
        "logreg_accept_rate": float(accept.mean()) if n else 0.0,
        "llm_fallback_rate": float((~accept).mean()) if n else 1.0,
    }
    labeled = scored[scored["label_train"].notna()].copy()
    if not labeled.empty:
        acc_mask = accept_mask(labeled, tau, margin)
        out["labeled_accuracy_classifier"] = float(
            (labeled["pred"].astype(str) == labeled["label_train"].astype(str)).mean()
        )
        if acc_mask.any():
            sub = labeled.loc[acc_mask]
            out["labeled_accuracy_on_accepted"] = float(
                (sub["pred"].astype(str) == sub["label_train"].astype(str)).mean()
            )
        else:
            out["labeled_accuracy_on_accepted"] = 0.0
        out["labeled_accept_rate"] = float(acc_mask.mean())
        out["labeled_llm_fallback_rate"] = float((~acc_mask).mean())
    if include_priority:
        pl = priority_labels or PRIORITY_COARSE_LABELS
        out.update(priority_metrics(scored, tau, margin, priority_labels=pl))
    return out


def _classification_block(y_true: pd.Series, y_pred: pd.Series) -> tuple[float, dict, pd.DataFrame]:
    labels = sorted(set(y_true.unique()) | set(y_pred.unique()))
    macro = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    report = classification_report(y_true, y_pred, labels=labels, zero_division=0, output_dict=True)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    cm_df = pd.DataFrame(cm, index=labels, columns=labels)
    return float(macro), report, cm_df


def evaluate_test(
    test_df: pd.DataFrame,
    model,
    tau: float,
    margin: float,
    *,
    report_priority: bool = False,
    priority_labels: frozenset[str] | None = None,
) -> tuple[dict, pd.DataFrame]:
    scored = predict_frame(model, test_df)
    scored["pred_with_reject"] = apply_reject(scored, tau, margin)
    labeled = scored[scored["label_train"].notna()].copy()
    y_true = labeled["label_train"].astype(str)
    y_classifier = labeled["pred"].astype(str)
    y_routed = labeled["pred_with_reject"].astype(str)

    macro_f1_classifier, report_classifier, _ = _classification_block(y_true, y_classifier)
    macro_f1, report, cm_df = _classification_block(y_true, y_routed)

    per_class_rr = routing_recall_by_class(labeled, tau, margin)
    per_class_f1 = routing_f1_by_class(labeled, tau, margin)
    min_f1 = float(min(per_class_f1.values())) if per_class_f1 else 0.0
    auc = prob_auc_metrics(labeled, model)
    routing = routing_metrics(
        scored,
        tau,
        margin,
        include_priority=report_priority,
        priority_labels=priority_labels,
    )
    routing["min_routing_f1"] = min_f1

    metrics: dict = {
        "macro_f1": macro_f1,
        "macro_f1_classifier": macro_f1_classifier,
        "classification_report": report,
        "classification_report_classifier": report_classifier,
        "macro_recall": float(report.get("macro avg", {}).get("recall") or 0.0),
        "macro_recall_classifier": float(report_classifier.get("macro avg", {}).get("recall") or 0.0),
        "routing_f1_per_class": per_class_f1,
        "min_routing_f1": min_f1,
        "routing_recall_per_class": per_class_rr,
        "auc": auc,
        "routing": routing,
    }
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