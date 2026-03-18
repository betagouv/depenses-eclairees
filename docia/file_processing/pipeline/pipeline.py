"""
Pipeline module for document processing workflow management.
Handles batch processing of documents through various processing steps including text extraction,
classification, and information extraction using Celery tasks.
"""

import logging
import uuid
from datetime import datetime

from django.db import models
from django.db.transaction import atomic
from django.utils import timezone

from celery import chain, group, shared_task
from celery.result import GroupResult

from docia.documents.models import DataEngagement
from docia.file_processing.models import (
    BATCH_STUCK_TIMEOUT,
    ProcessDocumentBatch,
    ProcessDocumentJob,
    ProcessDocumentStep,
    ProcessDocumentStepType,
    ProcessingStatus,
)
from docia.file_processing.pipeline.steps.classification import task_classify_document
from docia.file_processing.pipeline.steps.content_analysis import SUPPORTED_DOCUMENT_TYPES, task_analyze_content
from docia.file_processing.pipeline.steps.init_documents import (
    init_documents_from_external_filter_by_num_ejs,
    init_documents_in_folder,
)
from docia.file_processing.pipeline.steps.text_extraction import task_extract_text
from docia.file_processing.sync.workflow import sync_all, sync_documents_and_download_files
from docia.models import Document

logger = logging.getLogger(__name__)


DEFAULT_PROCESS_STEPS = [
    ProcessDocumentStepType.TEXT_EXTRACTION,
    ProcessDocumentStepType.CLASSIFICATION,
    ProcessDocumentStepType.CONTENT_ANALYSIS,
]


def launch_batch(
    *,
    folder: str = None,
    step_types: list[ProcessDocumentStepType] = None,
    target_classifications: list[str] = None,
    qs_documents: models.QuerySet | None = None,
    batch_id: str | None = None,
    retry_of: ProcessDocumentBatch | None = None,
) -> (ProcessDocumentBatch, GroupResult):
    """
    Launch a batch processing job for documents with specified processing steps.
    Creates a batch processing job that runs multiple processing steps on a set of documents in parallel.

    Args:
        folder: Optional directory path to filter documents
        step_types: List of processing step types to perform (text extraction, classification, etc.)
        target_classifications: Only process documents with these classification labels
        qs_documents: Optional pre-filtered document queryset to process specific documents
        batch_id: Optional UUID to use for the batch instead of generating one
        retry_of: Optional reference to original ProcessDocumentBatch being retried

    Returns:
        tuple: (ProcessDocumentBatch, Celery GroupResult)
    """

    # Get all documents if no queryset provided
    if qs_documents is None:
        qs_documents = Document.objects.all()

    # Filter documents by folder if specified
    if folder:
        qs_documents = qs_documents.filter(file__startswith=folder)

    # Use default processing steps if none specified
    if step_types is None:
        step_types = DEFAULT_PROCESS_STEPS

    # Use default document types to process if none specified
    if target_classifications is None:
        target_classifications = SUPPORTED_DOCUMENT_TYPES

    # Create the batch processing record
    batch = ProcessDocumentBatch(
        folder=folder,
        target_classifications=target_classifications,
        steps=step_types,
        status=ProcessingStatus.STARTED,
        celery_task_id=str(uuid.uuid4()),
        retry_of=retry_of,
    )
    if batch_id:
        batch.id = batch_id

    # Initialize lists to store jobs, steps and tasks
    jobs = []
    steps = []
    job_tasks = []
    for document in qs_documents:
        job = ProcessDocumentJob(
            batch=batch,
            document=document,
            status=ProcessingStatus.PENDING,
            celery_task_id=str(uuid.uuid4()),
        )
        jobs.append(job)
        step_tasks = []
        for i, step_type in enumerate(step_types):
            step = ProcessDocumentStep(
                job=job,
                step_type=step_type,
                order=i + 1,
                status=ProcessingStatus.PENDING,
                celery_task_id=str(uuid.uuid4()),
            )
            steps.append(step)
            step_task = task_from_step_type(step_type).si(step.id).set(task_id=step.celery_task_id)
            step_tasks.append(step_task)
        job_tasks.append(chain(*step_tasks).set(task_id=job.celery_task_id))

    with atomic():
        batch.save()
        ProcessDocumentJob.objects.bulk_create(jobs)
        ProcessDocumentStep.objects.bulk_create(steps)

    r = group(job_tasks).set(task_id=batch.celery_task_id)()
    return batch, r


def retry_batch_failures(batch_id: str, retry_cancelled: bool = False) -> (ProcessDocumentBatch, GroupResult):
    """Launch a new batch for failed documents in a previous batch.

    All steps will be retried, regardless of their status.

    Args:
        batch_id: UUID of the batch to retry failed jobs from
        retry_cancelled: If True, also retry cancelled jobs in addition to failed ones

    Returns:
        tuple: (ProcessDocumentBatch, GroupResult) - New batch and its Celery group result
    """
    batch = ProcessDocumentBatch.objects.get(id=batch_id)
    status_to_retry = [ProcessingStatus.FAILURE]
    if retry_cancelled:
        status_to_retry.append(ProcessingStatus.CANCELLED)
    jobs_to_retry = batch.job_set.filter(status__in=status_to_retry)
    qs_documents = Document.objects.filter(processdocumentjob__in=jobs_to_retry).distinct()
    return launch_batch(
        folder=batch.folder,
        step_types=batch.steps,
        target_classifications=batch.target_classifications,
        qs_documents=qs_documents,
        retry_of=batch,
    )


def close_and_retry_stuck_batches(timeout_seconds: int = BATCH_STUCK_TIMEOUT) -> list[tuple[str, str]]:
    stuck_batches = ProcessDocumentBatch.objects.filter_stuck_batches(timeout_seconds=timeout_seconds)
    results = []
    for batch in stuck_batches:
        logger.info(f"Closing and retrying stuck batch {batch.id} (last update: {batch.last_job_step_finished_at})")
        cancel_batch(batch.id)
        new_batch, _ = retry_batch_failures(batch.id, retry_cancelled=True)
        logger.info(f"New batch {new_batch.id} launched for stuck batch {batch.id}")
        results.append((batch.id, new_batch.id))
    return results


def task_from_step_type(step_type: ProcessDocumentStepType):
    """
    Map processing step type to the corresponding Celery task.
    """
    if step_type == ProcessDocumentStepType.TEXT_EXTRACTION:
        return task_extract_text
    elif step_type == ProcessDocumentStepType.CLASSIFICATION:
        return task_classify_document
    elif step_type == ProcessDocumentStepType.CONTENT_ANALYSIS:
        return task_analyze_content
    else:
        raise ValueError(f"Unknown step type {step_type}")


def cancel_batch(batch_id: str):
    """
    Cancel a running batch processing job and its associated tasks.

    Args:
        batch_id: UUID of the batch to cancel

    Updates all pending jobs and steps to cancelled status.
    """
    status_to_cancel = [ProcessingStatus.PENDING, ProcessingStatus.STARTED]
    now = timezone.now()
    with atomic():
        ProcessDocumentStep.objects.filter(job__batch_id=batch_id).filter(status__in=status_to_cancel).update(
            status=ProcessingStatus.CANCELLED,
            updated_at=now,
        )
        ProcessDocumentJob.objects.filter(batch_id=batch_id).filter(status__in=status_to_cancel).update(
            status=ProcessingStatus.CANCELLED,
            updated_at=now,
        )
        batch = ProcessDocumentBatch.objects.get(id=batch_id)
        batch.status = ProcessingStatus.CANCELLED
        batch.save()


@shared_task
def task_launch_batch(
    *, folder: str = None, step_types=None, target_classifications: list[str] = None, batch_id: str | None = None
):
    launch_batch(folder=folder, step_types=step_types, target_classifications=target_classifications, batch_id=batch_id)


def init_documents_and_launch_batch(folder: str, batch_grist: str, target_classifications: list[str] = None):
    batch_id = str(uuid.uuid4())
    gr = init_documents_in_folder(
        folder,
        batch_grist,
        on_success=task_launch_batch.si(
            folder=folder, target_classifications=target_classifications, batch_id=batch_id
        ),
    )
    return batch_id, gr


def sync_and_analyze(start: datetime, end: datetime = None, force_analyze: bool = False) -> str:
    """
    Synchronize documents within a date range and analyze them.

    Args:
        start: Start datetime for synchronization
        end: Optional end datetime for synchronization (defaults to now)
        force_analyze: If True, re-analyze already processed documents

    Returns:
        str: Batch ID of the launched processing batch
    """
    logger.info("Start sync and analyze (by date)")
    logger.info("Start sync")
    sync_result = sync_all(start, end)
    logger.info("Sync success:")
    for k, v in sync_result.items():
        logger.info(f"{k}: {v}")
    num_ejs = sync_result["num_ejs"]
    return _init_and_launch_batch(num_ejs, force_analyze=force_analyze)


def sync_and_analyze_ej_list(num_ejs: list[str], force_analyze: bool = False) -> str:
    """
    Synchronize and analyze documents for a specific list of engagement numbers.

    Args:
        num_ejs: List of engagement numbers to process
        force_analyze: If True, re-analyze already processed documents

    Returns:
        str: Batch ID of the launched processing batch
    """
    logger.info("Start sync and analyze (by ej list)")
    logger.info("Create or update all EJs")
    n = DataEngagement.objects.bulk_create(
        (DataEngagement(num_ej=num_ej) for num_ej in num_ejs),
        ignore_conflicts=True,
    )
    logger.info("Successfully updated EJs (%s)", n)
    sync_documents_and_download_files(num_ejs)
    return _init_and_launch_batch(num_ejs, force_analyze=force_analyze)


def _init_and_launch_batch(num_ejs: list[str], force_analyze: bool = False) -> str:
    logger.info("Init documents...")
    batch_name = f"auto-{timezone.now().isoformat()}"
    init_documents_from_external_filter_by_num_ejs(num_ejs, batch_name)

    logger.info("Launch batch...")
    qs_docs = Document.objects.filter(engagements__num_ej__in=num_ejs).distinct()

    if not force_analyze:
        # Ignore already processed
        qs_docs = qs_docs.filter(structured_data__isnull=True)

    batch, r = launch_batch(qs_documents=qs_docs)
    return batch.id
