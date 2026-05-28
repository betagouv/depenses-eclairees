from __future__ import annotations

from docia.file_processing.processor import synthesis as syn


def _pj(
    classification: str,
    filename: str,
    data: dict,
    *,
    hash_: str = "",
) -> syn.PieceJointe:
    return syn.PieceJointe(
        filename=filename,
        classification=classification,
        structured_data=data,
        hash=hash_,
    )


def test_best_pj_per_classification_keeps_most_filled():
    sparse = _pj("devis", "a.pdf", {"objet": "A"})
    rich = _pj("devis", "b.pdf", {"objet": "B", "siret": "1"})
    got = syn.best_pj_per_classification([sparse, rich])
    assert got["devis"].filename == "b.pdf"


def test_best_pj_per_classification_tiebreak_filename():
    a = _pj("devis", "a.pdf", {"objet": "A", "x": 1})
    b = _pj("devis", "b.pdf", {"objet": "B", "y": 1})
    got = syn.best_pj_per_classification([a, b])
    assert got["devis"].filename == "a.pdf"


def test_synthesize_row_objet_from_ej_ae():
    row = syn.EjContratRow(num_ej="1000000001")
    attachments = syn.AttachmentsByScope(
        ej=[
            _pj("acte_engagement", "ae.pdf", {"objet_marche": "Marché"}),
        ],
    )
    result = syn.synthesize_row(row, attachments)
    assert result.objet == "Marché"
    assert result.source_et_conflits is not None
    assert any(x["valeur"] == "Marché" for x in result.source_et_conflits["objet"])


def test_synthesize_row_fallback_contrat_when_ej_empty():
    row = syn.EjContratRow(num_ej="1000000001", contrat="2000000002")
    attachments = syn.AttachmentsByScope(
        ej=[],
        contrat=[
            _pj("acte_engagement", "c_ae.pdf", {"objet_marche": "Contrat"}),
        ],
    )
    result = syn.synthesize_row(row, attachments)
    assert result.objet == "Contrat"
    assert result.source_et_conflits["objet"][0]["source"] == "c_ae.pdf"


def test_synthesize_row_ej_preferred_over_contrat():
    row = syn.EjContratRow(num_ej="1000000001", contrat="2000000002")
    attachments = syn.AttachmentsByScope(
        ej=[_pj("devis", "ej.pdf", {"objet": "EJ"})],
        contrat=[_pj("devis", "marche.pdf", {"objet": "Marché"})],
    )
    result = syn.synthesize_row(row, attachments)
    assert result.objet == "EJ"


def test_synthesize_row_none_when_no_sources():
    row = syn.EjContratRow(num_ej="1000000001")
    result = syn.synthesize_row(row, syn.AttachmentsByScope())
    assert result.objet is None
    assert result.source_et_conflits is None


def test_read_ej_contrat_csv(tmp_path):
    path = tmp_path / "ej.csv"
    path.write_text("num_ej;contrat\n1000000001;2000000002\n", encoding="utf-8")
    rows = syn.read_ej_contrat_csv(str(path))
    assert len(rows) == 1
    assert rows[0].num_ej == "1000000001"
    assert rows[0].contrat == "2000000002"
