import datetime
from unittest.mock import patch

import pytest

from docia.file_processing.models import ExternalDocumentMetadata, ExternalLinkDocumentOrder
from docia.file_processing.sync.client import ApiDocumentMetadata
from docia.file_processing.sync.sync_metadata import DocumentMetadataSync
from tests.factories.file_processing import ExternalDocumentMetadataFactoryWithOrder
from tests.utils import bind_arguments


@pytest.fixture
def syncer():
    syncer = DocumentMetadataSync()
    syncer.client.is_authenticated = True
    yield syncer


def dt(year, month, day):
    return datetime.datetime(year, month, day, tzinfo=datetime.timezone.utc)


@pytest.mark.django_db
def test_sync(syncer):
    """Test that documents and their links are correctly created in the database during sync."""
    # Setup
    order_id = "1234567890"
    order_id_2 = "2234567890"
    api_docs = [
        ApiDocumentMetadata(id="0001", name="doc1.pdf", num_ej=order_id, size=100, date=dt(2026, 3, 15)),
        ApiDocumentMetadata(id="0002", name="doc2.pdf", num_ej=order_id, size=100, date=dt(2026, 3, 15)),
        ApiDocumentMetadata(id="0003", name="doc3.pdf", num_ej=order_id_2, size=100, date=dt(2026, 3, 15)),
    ]

    # Mock
    def m_list_documents_for_ej(*args, **kwargs):
        bound_args = bind_arguments(syncer.client.list_documents_for_ej, *args, **kwargs)
        num_ej = bound_args["num_ej"]
        return [doc for doc in api_docs if doc.num_ej == num_ej]

    # Function call
    with patch.object(syncer.client, "list_documents_for_ej", autospec=True, side_effect=m_list_documents_for_ej):
        synced_doc_ids = syncer.sync([order_id, order_id_2])

    # Asserts
    assert synced_doc_ids == sorted([api_doc.id for api_doc in api_docs])

    inserted_docs = list(
        ExternalDocumentMetadata.objects.order_by("name").values("external_id", "name", "size", "date")
    )
    expected_docs = [{"external_id": doc.id, "name": doc.name, "size": doc.size, "date": doc.date} for doc in api_docs]
    assert inserted_docs == expected_docs

    inserted_links = list(
        ExternalLinkDocumentOrder.objects.order_by("external_document_id").values("external_document_id", "order_id")
    )
    expected_links = [{"external_document_id": doc.id, "order_id": doc.num_ej} for doc in api_docs]
    assert inserted_links == expected_links


@pytest.mark.django_db
def test_sync_update(syncer):
    """Test that existing documents are updated and new links are created during sync."""
    # Setup
    order_id = "1234567890"
    # Existing doc
    existing_order_id = "2234567890"
    existing_doc = ExternalDocumentMetadataFactoryWithOrder(link__order_id=existing_order_id)
    # Api return same doc but with different order link
    api_doc = ApiDocumentMetadata(
        id=existing_doc.external_id,
        name=existing_doc.name,
        num_ej=order_id,
        size=existing_doc.size,
        date=dt(2026, 3, 15),
    )

    # Function call
    with patch.object(syncer.client, "list_documents_for_ej", autospec=True) as m_list:
        m_list.return_value = [api_doc]
        synced_doc_ids = syncer.sync([order_id])

    # Asserts
    assert synced_doc_ids == [api_doc.id]

    db_docs = list(ExternalDocumentMetadata.objects.values("external_id", "name", "size", "date"))
    expected_docs = [{"external_id": api_doc.id, "name": api_doc.name, "size": api_doc.size, "date": api_doc.date}]
    assert db_docs == expected_docs

    db_links = list(ExternalLinkDocumentOrder.objects.order_by("created_at").values("external_document_id", "order_id"))
    expected_links = [
        {"external_document_id": existing_doc.external_id, "order_id": existing_order_id},
        {"external_document_id": api_doc.id, "order_id": api_doc.num_ej},
    ]
    assert db_links == expected_links


@pytest.mark.django_db
def test_sync_handle_duplicates(syncer):
    # Setup
    order_id = "1234567890"
    order_id_2 = "2234567890"
    api_doc_to_keep = ApiDocumentMetadata(id="0001", name="doc1.pdf", num_ej=order_id, size=100, date=dt(2026, 3, 15))
    api_docs = [
        # Should be dumped (older)
        ApiDocumentMetadata(id="0001", name="doc1.pdf", num_ej=order_id, size=100, date=dt(2026, 3, 16)),
        # Should be kept (earlier)
        api_doc_to_keep,
        # Should be dumped (older), but link should be kept
        ApiDocumentMetadata(id="0001", name="doc1.pdf", num_ej=order_id_2, size=100, date=dt(2026, 3, 16)),
    ]

    # Mock
    def m_list_documents_for_ej(*args, **kwargs):
        bound_args = bind_arguments(syncer.client.list_documents_for_ej, *args, **kwargs)
        num_ej = bound_args["num_ej"]
        return [doc for doc in api_docs if doc.num_ej == num_ej]

    # Function call
    with patch.object(syncer.client, "list_documents_for_ej", autospec=True, side_effect=m_list_documents_for_ej):
        synced_doc_ids = syncer.sync([order_id, order_id_2])

    # Asserts
    assert synced_doc_ids == sorted(["0001"])

    inserted_docs = list(ExternalDocumentMetadata.objects.order_by("name").values("external_id", "date"))
    expected_docs = [{"external_id": api_doc_to_keep.id, "date": api_doc_to_keep.date}]
    assert inserted_docs == expected_docs

    inserted_links = list(
        ExternalLinkDocumentOrder.objects.order_by("external_document_id").values("external_document_id", "order_id")
    )
    expected_links = [
        {"external_document_id": "0001", "order_id": order_id},
        {"external_document_id": "0001", "order_id": order_id_2},
    ]
    assert inserted_links == expected_links
