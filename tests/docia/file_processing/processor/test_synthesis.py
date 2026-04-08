"""Tests sans base de données pour ``docia.file_processing.processor.synthesis``."""

from __future__ import annotations

import pandas as pd

from docia.file_processing.processor import synthesis as syn


def _minimal_merged_row(
    num_ej: str = "1000000001",
    *,
    contrat=None,
    objet_marche: str | None = "Objet AE",
    filename_ae: str = "ae.pdf",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "num_ej": [num_ej],
            "contrat": [contrat],
            "structured_data": [{"objet_marche": objet_marche}],
            "filename_ae": [filename_ae],
        }
    )


def test_get_documents_from_engagements_empty_list():
    df = syn.get_documents_from_engagements([])
    assert df.empty
    assert list(df.columns) == [
        "hash",
        "filename",
        "engagements",
        "classification",
        "structured_data",
    ]


def test_merge_documents_and_engagements_acte_on_num_ej():
    df_ej = pd.DataFrame({"num_ej": ["1000000001"], "contrat": [None]})
    df_pj = pd.DataFrame(
        {
            "engagements": ["1000000001"],
            "classification": ["acte_engagement"],
            "structured_data": [{"objet_marche": "Libellé"}],
            "filename": ["ae.pdf"],
        }
    )
    out = syn.merge_documents_and_engagements(df_ej, df_pj)
    assert len(out) == 1
    assert out.iloc[0]["structured_data"] == {"objet_marche": "Libellé"}
    assert out.iloc[0]["filename_ae"] == "ae.pdf"


def test_merge_documents_and_engagements_contrat_column():
    df_ej = pd.DataFrame({"num_ej": ["1000000001"], "contrat": ["2000000002"]})
    df_pj = pd.DataFrame(
        {
            "engagements": ["2000000002"],
            "classification": ["acte_engagement"],
            "structured_data": [{"objet_marche": "Contrat"}],
            "filename": ["c_ae.pdf"],
        }
    )
    out = syn.merge_documents_and_engagements(df_ej, df_pj)
    assert out.iloc[0]["structured_data_ae_contrat"] == {"objet_marche": "Contrat"}
    assert out.iloc[0]["filename_ae_contrat"] == "c_ae.pdf"


def test_get_field_with_sources_objet_from_ae():
    row = pd.Series(
        {
            "structured_data": {"objet_marche": "X"},
            "filename_ae": "a.pdf",
        }
    )
    got = syn.get_field_with_sources(row, syn.OBJET_SOURCES)
    assert got == [{"valeur": "X", "source": "a.pdf"}]


def test_apply_synthesis_fields_none_when_no_sources():
    df = _minimal_merged_row(objet_marche=None)
    df["structured_data"] = [None]
    df["filename_ae"] = [None]
    out = syn.apply_synthesis_fields(df)
    assert out.iloc[0]["source_et_conflits"] is None
    assert out.iloc[0]["objet"] is None


def test_apply_synthesis_fields_output_columns_order():
    df = _minimal_merged_row()
    out = syn.apply_synthesis_fields(df)
    assert list(out.columns) == [c for c in syn.SYNTHESIS_OUTPUT_COLUMNS if c in out.columns]


def test_apply_synthesis_fields_objet_and_conflicts():
    df = _minimal_merged_row(objet_marche="Marché", filename_ae="doc.pdf")
    out = syn.apply_synthesis_fields(df)
    assert out.iloc[0]["objet"] == "Marché"
    conf = out.iloc[0]["source_et_conflits"]
    assert conf is not None
    assert any(x["valeur"] == "Marché" for x in conf["objet"])
