from unittest.mock import patch

import pandas as pd

from docia.file_processing.processor.classify.grist_test_db_enrich import (
    enrich_test_final_from_db,
    resolve_hashes,
)


def test_resolve_hashes_from_v2_parquet(tmp_path):
    df = pd.DataFrame({"filename": ["a.pdf"], "num_ej": ["EJ1"], "hash": [None]})
    v2 = pd.DataFrame({"filename": ["a.pdf"], "num_ej": ["EJ1"], "hash": ["abc123"]})
    p = tmp_path / "documents_raw.parquet"
    v2.to_parquet(p, index=False)
    hashes, stats = resolve_hashes(df, classify_v2_parquet=p, resolve_filename_ej=False)
    assert hashes.iloc[0] == "abc123"
    assert stats["from_v2"] == 1


@patch("docia.file_processing.processor.classify.grist_test_db_enrich._fetch_by_hashes")
@patch("docia.file_processing.processor.classify.grist_test_db_enrich.resolve_hashes")
def test_enrich_fills_missing_fields(mock_resolve, mock_fetch):
    df = pd.DataFrame(
        {
            "filename": ["a.pdf"],
            "num_ej": [None],
            "is_ocr": [None],
            "hash": ["h1"],
        }
    )
    mock_resolve.return_value = (
        pd.Series(["h1"], index=df.index),
        {"from_grist": 1, "from_v2": 0, "from_db_filename": 0, "unresolved": 0},
    )
    mock_fetch.return_value = {
        "h1": {
            "document_id": "uuid-1",
            "hash": "h1",
            "nb_mot": 120,
            "num_ej": "EJ9",
            "dossier": "/d",
            "extension": "pdf",
            "nb_pages": 2,
            "is_ocr": True,
            "classification_prod": "devis",
            "ratio_extracted": 0.5,
            "analyzed_at": "2026-01-01T00:00:00+00:00",
            "filename_normalized": "a.pdf",
        }
    }
    out, meta = enrich_test_final_from_db(df, resolve_filename_ej=False)
    assert out.iloc[0]["document_id"] == "uuid-1"
    assert out.iloc[0]["nb_mot"] == 120
    assert out.iloc[0]["num_ej"] == "EJ9"
    assert out.iloc[0]["classification_prod"] == "devis"
    assert bool(out.iloc[0]["in_database"])
    assert meta["rows_with_document"] == 1