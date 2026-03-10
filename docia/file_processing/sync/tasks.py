import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from celery import chain, shared_task

from docia.documents.models import DataEngagement
from docia.file_processing.models import ExternalDocumentMetadata
from docia.file_processing.sync.downloader import DocumentDownloader
from docia.file_processing.sync.sync_engagements import EngagementsSync
from docia.file_processing.sync.sync_metadata import DocumentMetadataSync

logger = logging.getLogger(__name__)


def _default_start_datetime(now: datetime = None) -> datetime:
    now = now or timezone.now()
    start = now - timedelta(days=7)
    return start


def sync_all_externals(start: datetime = None):
    start = start or _default_start_datetime()
    return chain(
        sync_engagements.si(start=start),
        sync_documents.si(start=start),
        download_documents.si(start=start),
    )()


@shared_task(name="docia.sync_all_externals")
def task_sync_all_externals():
    sync_all_externals()


@shared_task(name="docia.sync_engagements")
def sync_engagements(start: datetime = None):
    scopes = settings.FILE_SYNC_SCOPES
    t_scopes = [s.split("/") for s in scopes]
    now = timezone.now()
    start = start or _default_start_datetime(now)

    ej_syncer = EngagementsSync()
    ej_syncer.sync(t_scopes, start, now)


@shared_task(name="docia.sync_documents")
def sync_documents(start: datetime = None):
    start = start or _default_start_datetime()
    qs = DataEngagement.objects.filter(external_updated_at__gte=start)
    qs = qs.order_by("external_updated_at")
    order_ids = list(qs.values_list("num_ej", flat=True))
    doc_syncer = DocumentMetadataSync()
    doc_syncer.sync(order_ids)


@shared_task(name="docia.download_documents")
def download_documents(start: datetime = None):
    start = start or _default_start_datetime()
    qs_orders = DataEngagement.objects.filter(external_updated_at__gte=start).values_list("num_ej", flat=True)
    qs = ExternalDocumentMetadata.objects.filter(order_link__order_id__in=qs_orders)
    downloader = DocumentDownloader()

    CONCURRENCY = 10

    def _task_download(id, name):
        logger.info("Start download %s %s", id, name)
        downloader.download_document(id, name)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        future_to_doc = {executor.submit(_task_download, doc.external_id, doc.name): doc for doc in qs}
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
            else:
                logger.info("[%s/%s] Complete download %s %s", i + 1, len(future_to_doc), doc.external_id, doc.name)
