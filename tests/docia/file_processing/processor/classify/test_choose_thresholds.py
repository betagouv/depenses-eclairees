import numpy as np
import pandas as pd

from docia.file_processing.processor.classify.evaluate import choose_thresholds


class _ProbaByRowModel:
    classes_ = ["devis", "rib"]

    def __init__(self, probs: np.ndarray) -> None:
        self._probs = probs

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return np.array(["devis"] * len(x), dtype=object)

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        p = self._probs[: len(x)]
        return np.column_stack([1 - p, p])


def test_choose_thresholds_cap_reduces_llm_fallback():
    n = 100
    probs = np.concatenate([np.full(80, 0.35), np.full(20, 0.98)])
    df = pd.DataFrame(
        {
            "label_train": ["devis"] * n,
            "text_2000": ["x"] * n,
            "filename_normalized": ["f"] * n,
            "nb_mot": [10] * n,
        }
    )
    uncapped = choose_thresholds(df, _ProbaByRowModel(probs), max_llm_fallback_rate=None)
    capped = choose_thresholds(df, _ProbaByRowModel(probs), max_llm_fallback_rate=0.5)
    assert capped.routing["llm_fallback_rate"] <= 0.5 + 1e-6
    assert capped.constraint_met is True
    assert capped.tau <= uncapped.tau