import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from docia.documents.models import DataEngagement

from ..models import ExternalDocumentMetadata
from .downloader import DocumentDownloader
from .sync_engagements import EngagementsSync
from .sync_metadata import DocumentMetadataSync

logger = logging.getLogger(__name__)


def sync_all(start: datetime, end: datetime = None):
    num_ejs = sync_engagements(start, end)
    r = sync_documents_and_download_files(num_ejs)
    return {
        "num_ejs": num_ejs,
        **r,
    }


def sync_documents_and_download_files(num_ejs: list[str]):
    doc_ids = sync_documents(num_ejs)
    download_success, download_errors = download_documents(doc_ids)
    return {
        "doc_ids": doc_ids,
        "download_success": download_success,
        "download_errors": download_errors,
    }


def sync_engagements(start: datetime, end: datetime = None) -> list[str]:
    end = end or timezone.now()
    scopes = settings.FILE_SYNC_SCOPES
    t_scopes = [s.split("/") for s in scopes]

    ej_syncer = EngagementsSync()
    num_ejs = ej_syncer.sync(t_scopes, start, end)
    return num_ejs


def sync_documents(num_ejs: list[str]) -> list[str]:
    qs = DataEngagement.objects.filter(num_ej__in=num_ejs)
    qs = qs.order_by("external_updated_at")
    order_ids = list(qs.values_list("num_ej", flat=True))
    doc_syncer = DocumentMetadataSync()
    ids = doc_syncer.sync(order_ids)
    return ids


def download_documents(doc_ids: list[str]):
    qs = ExternalDocumentMetadata.objects.filter(external_id__in=doc_ids)
    downloader = DocumentDownloader()

    CONCURRENCY = 10

    success = []
    errors = []

    def _task_download(doc: ExternalDocumentMetadata):
        logger.info("Start download %s %s %sMo", doc.external_id, doc.name, doc.size_mo)
        max_retries = 2 if doc.size_mo < 21 else 0
        try:
            downloader.download_document(doc.external_id, doc.name, max_retries=max_retries)
        except Exception as exc:
            doc.error_set.create(message=str(exc))
            raise

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        future_to_doc = {executor.submit(_task_download, doc): doc for doc in qs}
        for i, future in enumerate(as_completed(future_to_doc)):
            doc = future_to_doc[future]
            try:
                future.result()
            except Exception as exc:
                logger.exception(
                    "[%s/%s] Error downloading document %s %s: %s",
                    i + 1,
                    len(future_to_doc),
                    doc.external_id,
                    doc.name,
                    exc,
                )
                errors.append(doc.external_id)
            else:
                logger.info("[%s/%s] Complete download %s %s", i + 1, len(future_to_doc), doc.external_id, doc.name)
                success.append(doc.external_id)

    return success, errors
