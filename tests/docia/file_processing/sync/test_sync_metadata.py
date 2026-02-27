from unittest.mock import patch

import pytest

from docia.file_processing.models import ExternalDocumentMetadata, ExternalLinkDocumentOrder
from docia.file_processing.sync.client import ApiDocumentMetadata
from docia.file_processing.sync.sync_metadata import DocumentMetadataSync
from tests.factories.file_processing import ExternalDocumentMetadataFactoryWithOrder


@pytest.fixture
def syncer():
    syncer = DocumentMetadataSync()
    syncer.client.is_authenticated = True
    yield syncer


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
        ExternalLinkDocumentOrder.objects.order_by("external_document_id").values(
            "external_document_id", "order_id"
        )
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
    api_doc = ApiDocumentMetadata(id=existing_doc.external_id, name=existing_doc.name, num_ej=order_id, size=existing_doc.size)

    # Function call
    with patch.object(syncer.client, "list_documents_for_ej", autospec=True) as m_list:
        m_list.return_value = [api_doc]
        syncer.sync([order_id])

    # Asserts
    db_docs = list(ExternalDocumentMetadata.objects.values("external_id", "name", "size"))
    expected_docs = [{"external_id": api_doc.id, "name": api_doc.name, "size": api_doc.size}]
    assert db_docs == expected_docs

    db_links = list(
        ExternalLinkDocumentOrder.objects.order_by("created_at").values("external_document_id", "order_id")
    )
    expected_links = [
        {"external_document_id": existing_doc.external_id, "order_id": existing_order_id},
        {"external_document_id": api_doc.id, "order_id": api_doc.num_ej},
    ]
    assert db_links == expected_links
