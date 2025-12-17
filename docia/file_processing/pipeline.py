"""
Pipeline module for document processing workflow management.
Handles batch processing of documents through various processing steps including text extraction,
classification, and information extraction using Celery tasks.
"""

import uuid

from django.db import models
from django.db.transaction import atomic

from celery import chain, group, shared_task
from celery.result import GroupResult

from ..models import DataAttachment
from .classification import task_classify_document
from .info_extraction import SUPPORTED_DOCUMENT_TYPES, task_extract_info
from .init_documents import init_documents_in_folder
from .models import (
    ProcessDocumentBatch,
    ProcessDocumentJob,
    ProcessDocumentStep,
    ProcessDocumentStepType,
    ProcessingStatus,
)
from .text_extraction import task_extract_text


def launch_batch(
    *,
    folder: str = None,
    step_types: list[str] = None,
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
        qs_documents = DataAttachment.objects.all()

    # Filter documents by folder if specified
    if folder:
        qs_documents = qs_documents.filter(file__startswith=folder)

    # Use default processing steps if none specified
    if step_types is None:
        step_types = [
            ProcessDocumentStepType.TEXT_EXTRACTION,
            ProcessDocumentStepType.CLASSIFICATION,
            ProcessDocumentStepType.INFO_EXTRACTION,
        ]

    # Use default document types to process if none specified
    if target_classifications is None:
        target_classifications = SUPPORTED_DOCUMENT_TYPES

    # Create the batch processing record
    batch = ProcessDocumentBatch(
        folder=folder,
        target_classifications=target_classifications,
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
        for step_type in step_types:
            step = ProcessDocumentStep(
                job=job,
                step_type=step_type,
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
    /!\ This function does not check the previous batch steps so
    all the default steps will be performed.

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
    qs_documents = DataAttachment.objects.filter(processdocumentjob__in=jobs_to_retry).distinct()
    return launch_batch(
        folder=batch.folder,
        target_classifications=batch.target_classifications,
        qs_documents=qs_documents,
        retry_of=batch,
    )


def task_from_step_type(step_type: ProcessDocumentStepType):
    """
    Map processing step type to the corresponding Celery task.
    """
    if step_type == ProcessDocumentStepType.TEXT_EXTRACTION:
        return task_extract_text
    elif step_type == ProcessDocumentStepType.CLASSIFICATION:
        return task_classify_document
    elif step_type == ProcessDocumentStepType.INFO_EXTRACTION:
        return task_extract_info
    else:
        raise ValueError(f"Unknown step type {step_type}")


def cancel_batch(batch_id: str):
    """
    Cancel a running batch processing job and its associated tasks.

    Args:
        batch_id: UUID of the batch to cancel

    Updates all pending jobs and steps to cancelled status.
    """
    with atomic():
        batch = ProcessDocumentBatch.objects.get(id=batch_id)
        batch.status = ProcessingStatus.CANCELLED
        batch.save()
        ProcessDocumentJob.objects.filter(batch=batch).filter(status=ProcessingStatus.PENDING).update(
            status=ProcessingStatus.CANCELLED
        )
        ProcessDocumentStep.objects.filter(job__batch=batch).filter(status=ProcessingStatus.PENDING).update(
            status=ProcessingStatus.CANCELLED
        )


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
