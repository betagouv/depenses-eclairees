import pandas as pd

from docia.file_processing.processor.classify.grist_test_train_align import align_with_train_schema


def test_align_merges_v2_by_hash(tmp_path):
    golden = pd.DataFrame(
        {
            "hash": ["h1", "h2"],
            "filename": ["a.pdf", "b.pdf"],
            "text": ["long text grist", "g2"],
            "label_coarse": ["devis", "rib"],
            "label_coarse_ok": [True, True],
        }
    )
    v2 = pd.DataFrame(
        {
            "hash": ["h1"],
            "id": ["uuid-1"],
            "text_2000": ["from silver"],
            "filename_normalized": ["a pdf"],
            "classification": ["devis"],
            "label_train": ["devis"],
            "nb_mot": [99],
            "split": ["train"],
        }
    )
    p = tmp_path / "documents_raw.parquet"
    v2.to_parquet(p, index=False)
    out, stats = align_with_train_schema(golden, classify_v2_parquet=p, fetch_text_from_db=False)
    row0 = out[out["hash"] == "h1"].iloc[0]
    row1 = out[out["hash"] == "h2"].iloc[0]
    assert row0["text_2000"] == "from silver"
    assert row0["id"] == "uuid-1"
    assert row0["nb_mot"] == 99
    assert bool(row0["in_classify_v2_parquet"])
    assert row0["label_train"] == "devis"
    assert row0["label_train_silver"] == "devis"
    assert row1["text_2000"] == "g2"
    assert stats["rows_from_v2_hash"] == 1