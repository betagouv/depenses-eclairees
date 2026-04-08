"""
Tests Django / ORM pour ``synthesis`` (nécessitent pytest-django et une base de test).

Lancer par exemple : ``pytest tests/docia/file_processing/processor/test_synthesis_django.py``
"""

from __future__ import annotations

from django.db import connection

import pytest

import pandas as pd

from docia.file_processing.processor import synthesis as syn
from docia.models import DataEngagement
from tests.factories.data import DataEngagementFactory, DocumentFactory


@pytest.mark.django_db
def test_sync_synthesis_to_engagements_updates_row():
    ej = DataEngagementFactory(num_ej="1111111111")

    df = pd.DataFrame(
        {
            "num_ej": ["1111111111"],
            "contrat": [None],
            "objet": ["Titre"],
            "description_prestations": ["Desc"],
            "date": ["01/01/2025"],
            "societe_principale": ["ACME"],
            "siret": ["12345678901234"],
            "administration_beneficiaire": ["Ministère"],
            "source_et_conflits": [{"objet": [{"valeur": "Titre", "source": "f.pdf"}]}],
        }
    )
    n, missing = syn.sync_synthesis_to_engagements(df)
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
    DataEngagementFactory(num_ej="2222222222")
    import pandas as pd

    df = pd.DataFrame(
        {
            "num_ej": ["2222222222", "9999999999"],
            "contrat": [None, None],
            "objet": ["A", "B"],
            "description_prestations": [None, None],
            "date": [None, None],
            "societe_principale": [None, None],
            "siret": [None, None],
            "administration_beneficiaire": [None, None],
            "source_et_conflits": [None, None],
        }
    )
    n, missing = syn.sync_synthesis_to_engagements(df)
    assert n == 1
    assert missing == 1


@pytest.mark.django_db
def test_sync_synthesis_to_engagements_duplicate_num_ej_keeps_last():
    ej = DataEngagementFactory(num_ej="3333333333")

    df = pd.DataFrame(
        {
            "num_ej": ["3333333333", "3333333333"],
            "contrat": [None, None],
            "objet": ["Premier", "Dernier"],
            "description_prestations": [None, None],
            "date": [None, None],
            "societe_principale": [None, None],
            "siret": [None, None],
            "administration_beneficiaire": [None, None],
            "source_et_conflits": [None, None],
        }
    )
    syn.sync_synthesis_to_engagements(df, duplicate_num_ej="last")
    ej.refresh_from_db()
    assert ej.designation == "Dernier"


@pytest.mark.django_db
def test_sync_synthesis_to_engagements_truncates_siret():
    ej = DataEngagementFactory(num_ej="4444444444")
    long_siret = "1" * 30

    df = pd.DataFrame(
        {
            "num_ej": ["4444444444"],
            "contrat": [None],
            "objet": [None],
            "description_prestations": [None],
            "date": [None],
            "societe_principale": [None],
            "siret": [long_siret],
            "administration_beneficiaire": [None],
            "source_et_conflits": [None],
        }
    )
    syn.sync_synthesis_to_engagements(df)
    ej.refresh_from_db()
    assert len(ej.siret) == DataEngagement._meta.get_field("siret").max_length


@pytest.mark.django_db
def test_get_documents_from_engagements_returns_rows_linked_to_ej():
    if connection.vendor != "postgresql":
        pytest.skip("Requête synthesis ORM avec jsonb + Window (PostgreSQL uniquement)")

    ej = DataEngagementFactory(num_ej="4242424242")
    doc = DocumentFactory(
        classification="devis",
        structured_data={"objet": "D", "x": 1},
    )
    doc.engagements.add(ej)

    df = syn.get_documents_from_engagements(["4242424242"])
    assert not df.empty
    assert (df["engagements"] == "4242424242").all()
    assert df.iloc[0]["classification"] == "devis"
