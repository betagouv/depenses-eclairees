import pandas as pd

from docia.file_processing.processor.classify.train import priority_undersample_train


def test_priority_classes_balanced_to_ae_reference():
    n_ae = 80
    df = pd.DataFrame(
        {
            "label_train": ["acte_engagement"] * n_ae
            + ["devis"] * 500
            + ["rib"] * 200,
            "text_2000": "x",
        }
    )
    out = priority_undersample_train(df, seed=42)
    assert (out["label_train"] == "acte_engagement").sum() == n_ae
    assert (out["label_train"] == "devis").sum() == n_ae
    assert (out["label_train"] == "rib").sum() == n_ae


def test_small_priority_class_kept_fully():
    df = pd.DataFrame(
        {
            "label_train": ["acte_engagement"] * 100 + ["avenant"] * 20 + ["outil_gestion"] * 1000,
            "text_2000": "x",
        }
    )
    out = priority_undersample_train(df, seed=42)
    assert (out["label_train"] == "avenant").sum() == 20
    assert (out["label_train"] == "acte_engagement").sum() == 100
    assert (out["label_train"] == "outil_gestion").sum() == 100