"""
Tests Django / ORM pour ``synthesis`` (nécessitent pytest-django et une base de test).

Lancer par exemple : ``pytest tests/docia/file_processing/processor/test_synthesis_django.py``
"""

from __future__ import annotations

import pytest

from docia.file_processing.processor import synthesis as syn
from docia.models import Engagement
from tests.factories.data import DocumentFactory, EngagementFactory


def _synthesis_dict(**kwargs) -> dict:
    base = {
        "num_ej": "1111111111",
        "contrat": None,
        "objet": None,
        "description_prestations": None,
        "date": None,
        "societe_principale": None,
        "siret": None,
        "administration_beneficiaire": None,
        "source_et_conflits": None,
    }
    base.update(kwargs)
    return base


@pytest.mark.django_db
def test_sync_synthesis_to_engagements_updates_row():
    ej = EngagementFactory(num_ej="1111111111")

    rows = [
        _synthesis_dict(
            objet="Titre",
            description_prestations="Desc",
            date="01/01/2025",
            societe_principale="ACME",
            siret="12345678901234",
            administration_beneficiaire="Ministère",
            source_et_conflits={"objet": [{"valeur": "Titre", "source": "f.pdf"}]},
        )
    ]
    n, missing = syn.sync_synthesis_to_engagements(rows)
    assert n == 1
    assert missing == 0
    ej.refresh_from_db()
    assert ej.designation == "Titre"
    assert ej.descriptif_prestations == "Desc"
    assert ej.date == "01/01/2025"
    assert ej.prestataire == "ACME"
    assert ej.siret == "12345678901234"
    assert ej.administration == "Ministère"
    assert ej.sources_et_conflits is not None


@pytest.mark.django_db
def test_sync_synthesis_to_engagements_counts_missing_num_ej():
    EngagementFactory(num_ej="2222222222")

    rows = [
        _synthesis_dict(num_ej="2222222222", objet="A"),
        _synthesis_dict(num_ej="9999999999", objet="B"),
    ]
    n, missing = syn.sync_synthesis_to_engagements(rows)
    assert n == 1
    assert missing == 1


@pytest.mark.django_db
def test_sync_synthesis_to_engagements_duplicate_num_ej_keeps_last():
    ej = EngagementFactory(num_ej="3333333333")

    rows = [
        _synthesis_dict(num_ej="3333333333", objet="Premier"),
        _synthesis_dict(num_ej="3333333333", objet="Dernier"),
    ]
    syn.sync_synthesis_to_engagements(rows, duplicate_num_ej="last")
    ej.refresh_from_db()
    assert ej.designation == "Dernier"


@pytest.mark.django_db
def test_sync_synthesis_to_engagements_truncates_siret():
    ej = EngagementFactory(num_ej="4444444444")
    long_siret = "1" * 30

    rows = [_synthesis_dict(num_ej="4444444444", siret=long_siret)]
    syn.sync_synthesis_to_engagements(rows)
    ej.refresh_from_db()
    assert len(ej.siret) == Engagement._meta.get_field("siret").max_length


@pytest.mark.django_db
def test_load_attachments_returns_linked_document():
    ej = EngagementFactory(num_ej="4242424242")
    doc = DocumentFactory(
        classification="devis",
        structured_data={"objet": "D", "x": 1},
    )
    doc.engagements.add(ej)

    attachments = syn.load_attachments("4242424242", None)
    assert len(attachments.ej) == 1
    assert attachments.ej[0].classification == "devis"
    assert attachments.ej[0].structured_data["objet"] == "D"


@pytest.mark.django_db
def test_sync_synthesis_accepts_synthesis_row():
    ej = EngagementFactory(num_ej="5555555555")
    row = syn.SynthesisRow(num_ej="5555555555", objet="Via dataclass")
    n, missing = syn.sync_synthesis_to_engagements([row])
    assert n == 1
    assert missing == 0
    ej.refresh_from_db()
    assert ej.designation == "Via dataclass"
