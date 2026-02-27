import logging

from django.db.transaction import atomic

from docia.file_processing.models import ExternalDocumentMetadata, ExternalLinkDocumentOrder

from .client import SyncClient

logger = logging.getLogger(__name__)


class DocumentMetadataSync:
    def __init__(self):
        self.client = SyncClient.from_settings()

    def sync(self, list_num_ej: list[str]):
        """Fetch and store metadata for all documents associated with the provided engagement numbers.

        Store results in ExternalDocumentMetadata.
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
            docs_metadata.extend(
                [
                    ExternalDocumentMetadata(
                        external_id=doc.id,
                        name=doc.name,
                        size=doc.size,
                    )
                    for doc in documents_data
                ]
            )
            links.extend(
                [
                    ExternalLinkDocumentOrder(
                        external_document_id=doc.id,
                        order_id=doc.num_ej,
                    )
                    for doc in documents_data
                ]
            )
        logger.info("Fetched %s documents data, now inserting...", len(docs_metadata))
        with atomic():
            ExternalDocumentMetadata.objects.bulk_create(
                docs_metadata,
                batch_size=1000,
                update_conflicts=True,
                update_fields=["name", "size"],
                unique_fields=["external_id"],
            )
            ExternalLinkDocumentOrder.objects.bulk_create(links, batch_size=1000, ignore_conflicts=True)
        logger.info("Success: %s documents data inserted", len(docs_metadata))
