import pandas as pd

from docia.file_processing.processor.classify.evaluate import priority_capture_rate, priority_metrics


def test_priority_capture_counts_reject_as_miss():
    scored = pd.DataFrame(
        {
            "label_train": ["acte_engagement", "devis", "rib"],
            "pred": ["acte_engagement", "catalogue_prix", "rib"],
            "max_proba": [0.99, 0.99, 0.4],
            "margin": [0.5, 0.5, 0.1],
        }
    )
    tau, margin = 0.5, 0.05
    # devis mal classé = miss ; rib rejeté (proba basse) = miss → 1/3
    assert priority_capture_rate(scored, tau, margin) == 1 / 3
    m = priority_metrics(scored, tau, margin)
    assert m["priority_capture_rate"] == 1 / 3