import logging

from django.db.transaction import atomic

from docia.file_processing.models import ExternalDocumentMetadata, ExternalLinkDocumentOrder

from .client import ApiDocumentMetadata, SyncClient

logger = logging.getLogger(__name__)


class DocumentMetadataSync:
    def __init__(self):
        self.client = SyncClient.from_settings()

    def sync(self, list_num_ej: list[str]) -> list[str]:
        """Fetch and store metadata for all documents associated with the provided engagement numbers.

        Store results in ExternalDocumentMetadata.
        Returns the list of doc external ids insterted/updated.
        """

        if not self.client.is_authenticated:
            self.client.authenticate()

        logger.info("Fetch documents data...")
        docs_metadata = []
        links = []
        for i, num_ej in enumerate(list_num_ej):
            if len(list_num_ej) > 50 and i % 50 == 0:
                logger.info("ej=%s/%s (%s documents)", i, len(list_num_ej), len(docs_metadata))
            documents_data = self.client.list_documents_for_ej(num_ej)
            db_docs = [self.convert_api_doc_to_db_doc(data) for data in documents_data]
            db_links = [self.convert_api_doc_to_db_link(data) for data in documents_data]
            docs_metadata.extend(db_docs)
            links.extend(db_links)
        docs_metadata = self.remove_duplicate_docs(docs_metadata)
        links = self.remove_duplicate_links(links)
        logger.info("Fetched %s documents data, now inserting...", len(docs_metadata))
        with atomic():
            ExternalDocumentMetadata.objects.bulk_create(
                docs_metadata,
                batch_size=1000,
                update_conflicts=True,
                update_fields=["name", "size", "date"],
                unique_fields=["external_id"],
            )
            ExternalLinkDocumentOrder.objects.bulk_create(links, batch_size=1000, ignore_conflicts=True)
        logger.info("Success: %s documents data inserted", len(docs_metadata))
        list_doc_ids = sorted(set([doc.external_id for doc in docs_metadata]))
        return list_doc_ids

    def convert_api_doc_to_db_doc(self, api_doc: ApiDocumentMetadata) -> ExternalDocumentMetadata:
        db_doc = ExternalDocumentMetadata(
            external_id=api_doc.id,
            name=api_doc.name,
            size=api_doc.size,
            date=api_doc.date,
        )
        return db_doc

    def convert_api_doc_to_db_link(self, api_doc: ApiDocumentMetadata) -> ExternalLinkDocumentOrder:
        db_link = ExternalLinkDocumentOrder(
            external_document_id=api_doc.id,
            order_id=api_doc.num_ej,
        )
        return db_link

    def remove_duplicate_docs(self, docs: list[ExternalDocumentMetadata]) -> list[ExternalDocumentMetadata]:
        """Deduplicate documents using external_id, keep older one in case of duplicate."""
        docs = sorted(docs, key=lambda doc: doc.date, reverse=True)
        unique_dict = {doc.external_id: doc for doc in docs}
        return list(unique_dict.values())

    def remove_duplicate_links(self, links: list[ExternalLinkDocumentOrder]) -> list[ExternalLinkDocumentOrder]:
        """Deduplicate links using (external_document_id, order_id)."""
        unique_dict = {(link.external_document_id, link.order_id): link for link in links}
        return list(unique_dict.values())
