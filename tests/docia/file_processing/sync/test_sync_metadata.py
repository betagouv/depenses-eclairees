from unittest.mock import patch

import pytest

from docia.file_processing.models import ExternalDocumentMetadata, ExternalLinkDocumentOrder
from docia.file_processing.sync.client import ApiDocumentMetadata
from docia.file_processing.sync.sync_metadata import DocumentMetadataSync


@pytest.fixture
def syncer():
    with patch("docia.file_processing.sync.client.SyncClient.authenticate", autospec=True) as m_authenticate:
        m_authenticate.return_value = None
        yield DocumentMetadataSync()


@pytest.mark.django_db
def test_sync(syncer):
    """Test that documents and their links are correctly created in the database during sync."""
    # Setup
    order_id = "1234567890"
    order_id_2 = "2234567890"
    api_docs = [
        ApiDocumentMetadata(id="0001", name="doc1.pdf", num_ej=order_id, size=100),
        ApiDocumentMetadata(id="0002", name="doc2.pdf", num_ej=order_id, size=100),
        ApiDocumentMetadata(id="0003", name="doc3.pdf", num_ej=order_id_2, size=100),
    ]

    # Function call
    with patch.object(syncer.client, "list_documents_for_ej", autospec=True) as m_list:
        m_list.return_value = api_docs
        syncer.sync([order_id])

    # Asserts
    inserted_docs = list(ExternalDocumentMetadata.objects.order_by("name").values("external_id", "name", "size"))
    expected_docs = [{"external_id": doc.id, "name": doc.name, "size": doc.size} for doc in api_docs]
    assert inserted_docs == expected_docs

    inserted_links = list(
        ExternalLinkDocumentOrder.objects.order_by("document_external_id").values(
            "document_external_id", "order_external_id"
        )
    )
    expected_links = [{"document_external_id": doc.id, "order_external_id": doc.num_ej} for doc in api_docs]
    assert inserted_links == expected_links


@pytest.mark.django_db
def test_sync_update(syncer):
    """Test that existing documents are updated and new links are created during sync."""
    # Setup
    order_id = "1234567890"
    db_doc = ExternalDocumentMetadata.objects.create(external_id="0001", name="doc1.pdf", size=100)
    db_link = ExternalLinkDocumentOrder.objects.create(
        document_external_id=db_doc.external_id, order_external_id="2234567890"
    )
    api_doc = ApiDocumentMetadata(id="0001", name="doc1_up.pdf", num_ej=order_id, size=101)

    # Function call
    with patch.object(syncer.client, "list_documents_for_ej", autospec=True) as m_list:
        m_list.return_value = [api_doc]
        syncer.sync([order_id])

    # Asserts
    db_docs = list(ExternalDocumentMetadata.objects.values("external_id", "name", "size"))
    expected_docs = [{"external_id": api_doc.id, "name": api_doc.name, "size": api_doc.size}]
    assert db_docs == expected_docs

    db_links = list(
        ExternalLinkDocumentOrder.objects.order_by("created_at").values("document_external_id", "order_external_id")
    )
    expected_links = [
        {"document_external_id": db_link.document_external_id, "order_external_id": db_link.order_external_id},
        {"document_external_id": api_doc.id, "order_external_id": api_doc.num_ej},
    ]
    assert db_links == expected_links
