import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.evaluate import evaluate_test


class _RowProbaModel:
    classes_ = ["devis", "rib"]

    def __init__(self, probs: np.ndarray) -> None:
        self._probs = probs

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        idx = np.argmax(self._probs[: len(x)], axis=1)
        return np.array(self.classes_)[idx]

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        return self._probs[: len(x)]


def test_macro_f1_counts_reject_as_miss():
    df = pd.DataFrame(
        {
            "label_train": ["devis", "rib"],
            "text_2000": ["a", "b"],
            "filename_normalized": ["a", "b"],
            "nb_mot": [1, 1],
        }
    )
    # rib: bonne classe mais rejet (max proba 0.45 < tau 0.5)
    probs = np.array([[0.99, 0.01], [0.4, 0.45]])
    metrics, _ = evaluate_test(df, _RowProbaModel(probs), tau=0.5, margin=0.0)
    assert metrics["macro_f1_classifier"] == 1.0
    assert metrics["macro_f1"] < metrics["macro_f1_classifier"]
    assert metrics["macro_recall"] < metrics["macro_recall_classifier"]
    assert metrics["classification_report"]["rib"]["recall"] == 0.0