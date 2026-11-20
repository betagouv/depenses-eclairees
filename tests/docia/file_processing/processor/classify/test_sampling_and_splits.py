import pandas as pd

from docia.file_processing.processor.classify.constants import TARGET_RATIO_MEDIAN
from docia.file_processing.processor.classify.dataset import dedupe_by_hash
from docia.file_processing.processor.classify.fill_ratio import compute_ratio_data_extraction
from docia.file_processing.processor.classify.label_policy import needs_annexe_financiere_merge
from docia.file_processing.processor.classify.splits import assign_splits, split_leakage_check
from docia.file_processing.processor.classify.text_prep import normalize_filename, prepare_text_head


def test_compute_ratio():
    assert compute_ratio_data_extraction({"a": 1, "b": None}) == 0.5
    assert compute_ratio_data_extraction(None) == 0.0


def test_dedupe_by_hash_keeps_richer_row():
    rows = [
        {"hash": "h1", "text_2000": "a", "analyzed_at": None, "ratio_extracted": 0.0},
        {"hash": "h1", "text_2000": "longer", "analyzed_at": True, "ratio_extracted": 0.8},
    ]
    out, dropped = dedupe_by_hash(rows)
    assert dropped == 1
    assert out[0]["ratio_extracted"] == 0.8


def test_text_prep():
    assert "devis" in prepare_text_head("DEVIS client 123")
    assert "pdf" in normalize_filename("Foo/Bar_DEVIS.PDF")


def test_ej_split_no_leakage():
    df = pd.DataFrame(
        [
            {
                "id": "1",
                "classification": "devis",
                "label_train": "devis",
                "num_ej": "1000000001",
                "text_2000": "devis",
                "filename_normalized": "devis",
                "nb_mot": 10,
            },
            {
                "id": "2",
                "classification": "devis",
                "label_train": "devis",
                "num_ej": "1000000001",
                "text_2000": "devis deux",
                "filename_normalized": "devis2",
                "nb_mot": 12,
            },
            {
                "id": "3",
                "classification": "rib",
                "label_train": "rib",
                "num_ej": "1000000002",
                "text_2000": "rib",
                "filename_normalized": "rib",
                "nb_mot": 5,
            },
            {
                "id": "4",
                "classification": "ccap",
                "label_train": "ccap",
                "num_ej": "1000000003",
                "text_2000": "ccap",
                "filename_normalized": "ccap",
                "nb_mot": 20,
            },
            {
                "id": "5",
                "classification": "sous_traitance",
                "label_train": "sous_traitance",
                "num_ej": "1000000004",
                "text_2000": "sous traitance",
                "filename_normalized": "st",
                "nb_mot": 3,
            },
            {
                "id": "6",
                "classification": "avenant",
                "label_train": "avenant",
                "num_ej": "1000000005",
                "text_2000": "avenant",
                "filename_normalized": "avenant",
                "nb_mot": 3,
            },
            {
                "id": "7",
                "classification": "acte_engagement",
                "label_train": "acte_engagement",
                "num_ej": "1000000006",
                "text_2000": "acte",
                "filename_normalized": "ae",
                "nb_mot": 3,
            },
            {
                "id": "8",
                "classification": "facture",
                "label_train": None,
                "num_ej": "1000000007",
                "text_2000": "facture",
                "filename_normalized": "facture",
                "nb_mot": 3,
            },
        ]
    )
    out, _ = assign_splits(df, seed=42)
    assert split_leakage_check(out) == []
    assert set(TARGET_RATIO_MEDIAN)  # reference constants import


def test_annexe_financiere_merge_trigger():
    assert needs_annexe_financiere_merge({"bordereau_prix": 3, "devis": 50})