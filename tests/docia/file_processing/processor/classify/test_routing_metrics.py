import pandas as pd

from docia.file_processing.processor.classify.evaluate import routing_metrics


def test_routing_metrics_separates_llm_fallback_from_classifier_accuracy():
    scored = pd.DataFrame(
        {
            "label_train": ["devis", "devis", "rib", "rib"],
            "pred": ["devis", "devis", "rib", "ccap"],
            "max_proba": [0.99, 0.99, 0.3, 0.99],
            "margin": [0.2, 0.2, 0.1, 0.2],
        }
    )
    tau, margin = 0.5, 0.05
    m = routing_metrics(scored, tau, margin, include_priority=False)
    assert m["llm_fallback_rate"] == 0.25
    assert m["logreg_accept_rate"] == 0.75
    assert m["labeled_accuracy_classifier"] == 0.75
    assert m["labeled_accuracy_on_accepted"] == 2 / 3