import pandas as pd

from docia.file_processing.processor.classify.grist_test_set import (
    _normalize_priority_row,
    enrich_coarse_labels,
    merge_and_dedupe,
)
from docia.file_processing.processor.classify.grist_test_sources import (
    CLASSIF_GT_SOURCE,
    GRIST_PRIORITY_QUALITY_SOURCES,
)
from tests_e2e.grist_api import parse_classification_list


def test_parse_classification_list_variants():
    assert parse_classification_list('["devis", "ccap"]') == ["devis", "ccap"]
    assert parse_classification_list(["rib", ""]) == ["rib"]
    assert parse_classification_list("") is None
    assert parse_classification_list('{"x": 1}') is None
    assert parse_classification_list("not json") is None
    assert parse_classification_list(None) is None


def test_normalize_priority_row_acte_engagement():
    ae = next(s for s in GRIST_PRIORITY_QUALITY_SOURCES if s.table == "Acte_engagement_gt")
    row = pd.Series(
        {
            "id": 42,
            "filename": "ae.pdf",
            "num_ej": "EJ1",
            "text": "body",
            "commentaire": "traité",
        }
    )
    out = _normalize_priority_row(row, ae)
    assert out["label_fine"] == "acte_engagement"
    assert out["implicit_label_fine"] == "acte_engagement"
    assert out["source_table"] == "Acte_engagement_gt"
    assert out["e2e_module"] == "test_quality_acte_engagement"


def test_merge_and_dedupe_priority_only():
    ae = GRIST_PRIORITY_QUALITY_SOURCES[0]
    frame = pd.DataFrame(
        [
            {
                "grist_record_id": 1,
                "filename": "only_ae.pdf",
                "num_ej": None,
                "text": "t",
                "label_fine": "acte_engagement",
                "source_table": ae.table,
                "implicit_label_fine": "acte_engagement",
            }
        ]
    )
    merged, conflicts, stats = merge_and_dedupe(pd.DataFrame(), [(ae, frame)])
    assert len(merged) == 1
    assert merged.iloc[0]["label_fine"] == "acte_engagement"
    assert conflicts.empty
    assert stats.rows_after_dedupe == 1


def test_merge_and_dedupe_classif_wins_label_on_conflict():
    ae = next(s for s in GRIST_PRIORITY_QUALITY_SOURCES if s.table == "Acte_engagement_gt")
    classif = pd.DataFrame(
        [
            {
                "grist_record_id": 10,
                "filename": "dup.pdf",
                "num_ej": "99",
                "text": "c",
                "label_fine": "devis",
                "source_table": CLASSIF_GT_SOURCE.table,
                "implicit_label_fine": None,
            }
        ]
    )
    ae_row = pd.DataFrame(
        [
            {
                "grist_record_id": 20,
                "filename": "dup.pdf",
                "num_ej": "99",
                "text": "a",
                "label_fine": "acte_engagement",
                "source_table": ae.table,
                "implicit_label_fine": "acte_engagement",
            }
        ]
    )
    merged, conflicts, stats = merge_and_dedupe(classif, [(ae, ae_row)])
    assert len(merged) == 1
    assert merged.iloc[0]["label_fine"] == "devis"
    assert bool(merged.iloc[0]["label_conflict"])
    assert "Classif_gt" in merged.iloc[0]["source_table"]
    assert "Acte_engagement_gt" in merged.iloc[0]["source_table"]
    assert len(conflicts) == 1
    assert stats.label_conflicts == 1


def test_enrich_coarse_labels_maps_known_fine():
    df = pd.DataFrame({"label_fine": ["rib", "unknown_label_xyz"]})
    out = enrich_coarse_labels(df)
    assert bool(out.iloc[0]["label_coarse_ok"])
    assert out.iloc[0]["label_coarse"] == "rib"
    assert not bool(out.iloc[1]["label_coarse_ok"])

