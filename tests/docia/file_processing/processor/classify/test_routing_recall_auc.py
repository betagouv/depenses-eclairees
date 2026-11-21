import numpy as np
import pandas as pd
import pytest

from docia.file_processing.processor.classify.evaluate import (
    class_routing_recall,
    prob_auc_metrics,
    routing_f1_by_class,
    routing_macro_f1,
    routing_recall_by_class,
)


class _StubModel:
    classes_ = ["devis", "acte_engagement"]

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        del x
        return np.array([[0.3, 0.7], [0.6, 0.4]], dtype=float)


def test_class_routing_recall_reject_is_fn():
    df = pd.DataFrame(
        {
            "label_train": ["acte_engagement", "acte_engagement", "acte_engagement"],
            "max_proba": [0.99, 0.50, 0.99],
            "margin": [0.5, 0.5, 0.5],
            "pred": ["acte_engagement", "acte_engagement", "devis"],
        }
    )
    rec = class_routing_recall(df, "acte_engagement", tau=0.9, margin=0.1)
    assert rec == pytest.approx(1 / 3)


def test_prob_auc_metrics_acte_engagement():
    labels = ["acte_engagement", "devis"] * 4
    p_ae = [0.9, 0.1, 0.85, 0.15, 0.8, 0.2, 0.75, 0.25]
    df = pd.DataFrame(
        {
            "label_train": labels,
            "p_devis": [1 - p for p in p_ae],
            "p_acte_engagement": p_ae,
            "max_proba": p_ae,
            "margin": [0.5] * 8,
            "pred": labels,
        }
    )
    auc = prob_auc_metrics(df, _StubModel())
    assert auc["auc_macro_ovr"] == 1.0
    assert auc["auc_acte_engagement"] == 1.0


def test_routing_recall_by_class_all_labels():
    df = pd.DataFrame(
        {
            "label_train": ["devis", "devis", "acte_engagement"],
            "max_proba": [0.99, 0.40, 0.99],
            "margin": [0.5, 0.5, 0.5],
            "pred": ["devis", "devis", "acte_engagement"],
        }
    )
    per = routing_recall_by_class(df, tau=0.9, margin=0.1)
    assert per["devis"] == pytest.approx(0.5)
    assert per["acte_engagement"] == 1.0


def test_routing_macro_f1_penalizes_reject():
    df = pd.DataFrame(
        {
            "label_train": ["devis", "rib"],
            "max_proba": [0.99, 0.40],
            "margin": [0.5, 0.5],
            "pred": ["devis", "rib"],
        }
    )
    f1 = routing_macro_f1(df, tau=0.5, margin=0.0)
    per = routing_f1_by_class(df, tau=0.5, margin=0.0)
    assert per["rib"] == 0.0
    assert f1 < 1.0