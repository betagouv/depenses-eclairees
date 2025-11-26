from datetime import date

import pytest

import pandas as pd

from app.data.db import bulk_create_attachments, bulk_create_batches, bulk_create_engagements
from docia.models import DataAttachment, DataBatch, DataEngagement
from docia.tests.factories.data import DataBatchFactory, DataEngagementFactory


@pytest.mark.django_db
def test_bulk_create_engagements():
    df = pd.DataFrame(
        {
            "num_EJ": ["EJ1", "EJ2", "EJ3"],
            "date_creation": ["2025-10-08", "2025-10-09", "2025-10-10"],
        }
    )
    bulk_create_engagements(df)
    engagements = list(DataEngagement.objects.all().order_by("num_ej").values("num_ej", "date_creation"))
    assert engagements == [
        {"num_ej": "EJ1", "date_creation": date(2025, 10, 8)},
        {"num_ej": "EJ2", "date_creation": date(2025, 10, 9)},
        {"num_ej": "EJ3", "date_creation": date(2025, 10, 10)},
    ]


@pytest.mark.django_db
def test_bulk_create_engagements_ignore_duplicates():
    existing_ej = DataEngagementFactory(num_ej="EJ1", date_creation=date(2025, 10, 1))
    df = pd.DataFrame(
        {
            "num_EJ": [existing_ej.num_ej, "EJ2"],
            "date_creation": [existing_ej.date_creation.isoformat(), "2025-10-09"],
        }
    )
    bulk_create_engagements(df)
    engagements = list(DataEngagement.objects.all().order_by("num_ej").values("num_ej", "date_creation"))
    # EJ1 should be untouched
    assert engagements == [
        {"num_ej": existing_ej.num_ej, "date_creation": existing_ej.date_creation},
        {"num_ej": "EJ2", "date_creation": date(2025, 10, 9)},
    ]


@pytest.mark.django_db
def test_bulk_create_batches():
    ej1, ej2, ej3 = DataEngagementFactory.create_batch(3)
    df = pd.DataFrame(
        {
            "Batch": ["Batch1", "Batch2", "Batch3"],
            "num_EJ": [ej1.num_ej, ej2.num_ej, ej3.num_ej],
        }
    )
    bulk_create_batches(df)
    batches = list(DataBatch.objects.all().order_by("batch").values("batch", "ej"))
    assert batches == [
        {"batch": "Batch1", "ej": ej1.num_ej},
        {"batch": "Batch2", "ej": ej2.num_ej},
        {"batch": "Batch3", "ej": ej3.num_ej},
    ]


@pytest.mark.django_db
def test_bulk_create_batches_ignore_duplicates():
    existing_batch = DataBatchFactory(batch="Batch1")
    ej = DataEngagementFactory()
    df = pd.DataFrame(
        {
            "Batch": [existing_batch.batch, "Batch2"],
            "num_EJ": [existing_batch.ej, ej.num_ej],
        }
    )
    bulk_create_batches(df)
    batches = list(DataBatch.objects.all().order_by("batch").values("batch", "ej"))
    assert batches == [
        {"batch": existing_batch.batch, "ej": existing_batch.ej_id},
        {"batch": "Batch2", "ej": ej.num_ej},
    ]


@pytest.mark.django_db
def test_bulk_create_attachments():
    ej1, ej2, ej3 = DataEngagementFactory.create_batch(3)
    df = pd.DataFrame(
        {
            "filename": ["file1.pdf", "file2.doc", "file3.png"],
            "extension": ["pdf", "doc", "png"],
            "dossier": ["dossier1", "dossier2", "dossier3"],
            "num_EJ": [ej1.num_ej, ej2.num_ej, ej3.num_ej],
            "date_creation": ["2025-10-05", "2025-10-06", "2025-10-07"],
            "taille": [100, 200, 300],
            "hash": ["hash1", "hash2", "hash3"],
        }
    )
    bulk_create_attachments(df)
    attachments = list(
        DataAttachment.objects.all()
        .order_by("file")
        .values("filename", "extension", "dossier", "ej_id", "date_creation", "taille", "hash", "file")
    )
    assert attachments == [
        {
            "filename": "file1.pdf",
            "extension": "pdf",
            "dossier": "dossier1",
            "ej_id": ej1.num_ej,
            "date_creation": date(2025, 10, 5),
            "taille": 100,
            "hash": "hash1",
            "file": "dossier1/file1.pdf",
        },
        {
            "filename": "file2.doc",
            "extension": "doc",
            "dossier": "dossier2",
            "ej_id": ej2.num_ej,
            "date_creation": date(2025, 10, 6),
            "taille": 200,
            "hash": "hash2",
            "file": "dossier2/file2.doc",
        },
        {
            "filename": "file3.png",
            "extension": "png",
            "dossier": "dossier3",
            "ej_id": ej3.num_ej,
            "date_creation": date(2025, 10, 7),
            "taille": 300,
            "hash": "hash3",
            "file": "dossier3/file3.png",
        },
    ]


@pytest.mark.django_db
def test_bulk_create_attachments_ignore_duplicates():
    ej = DataEngagementFactory()
    ej1, ej2 = DataEngagementFactory.create_batch(2)
    DataAttachment.objects.create(
        filename="file1.pdf",
        dossier="dossier1",
        file="dossier1/file1.pdf",
        extension="pdf",
        ej=ej,
        date_creation="2025-10-01",
        taille=42,
        hash="hash",
    )
    df = pd.DataFrame(
        {
            "filename": ["file1.pdf", "file2.doc"],
            "extension": ["pdf", "doc"],
            "dossier": ["dossier1", "dossier2"],
            "num_EJ": [ej1.num_ej, ej2.num_ej],
            "date_creation": ["2025-10-05", "2025-10-06"],
            "taille": [100, 200],
            "hash": ["hash1", "hash2"],
        }
    )
    bulk_create_attachments(df)
    attachments = list(
        DataAttachment.objects.all()
        .order_by("file")
        .values("filename", "extension", "dossier", "ej_id", "date_creation", "taille", "hash", "file")
    )
    assert attachments == [
        {
            "filename": "file1.pdf",
            "extension": "pdf",
            "dossier": "dossier1",
            "ej_id": ej.num_ej,
            "date_creation": date(2025, 10, 1),
            "taille": 42,
            "hash": "hash",
            "file": "dossier1/file1.pdf",
        },
        {
            "filename": "file2.doc",
            "extension": "doc",
            "dossier": "dossier2",
            "ej_id": ej2.num_ej,
            "date_creation": date(2025, 10, 6),
            "taille": 200,
            "hash": "hash2",
            "file": "dossier2/file2.doc",
        },
    ]
