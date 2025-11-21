import uuid

from django.db.transaction import atomic

from celery import chain, group

from ..models import DataAttachment
from .classification import task_classify_document
from .info_extraction import task_extract_info
from .models import (
    ProcessDocumentBatch,
    ProcessDocumentJob,
    ProcessDocumentStep,
    ProcessDocumentStepType,
    ProcessingStatus,
)
from .text_extraction import task_extract_text


def launch_batch(folder: str, step_types=None):
    if step_types is None:
        step_types = [
            ProcessDocumentStepType.TEXT_EXTRACTION,
            ProcessDocumentStepType.CLASSIFICATION,
            ProcessDocumentStepType.INFO_EXTRACTION,
        ]

    batch = ProcessDocumentBatch(
        folder=folder,
        status=ProcessingStatus.STARTED,
        celery_task_id=str(uuid.uuid4()),
    )

    jobs = []
    steps = []
    job_tasks = []
    for document in DataAttachment.objects.filter(file__startswith=folder):
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


def task_from_step_type(step_type: ProcessDocumentStepType):
    if step_type == ProcessDocumentStepType.TEXT_EXTRACTION:
        return task_extract_text
    elif step_type == ProcessDocumentStepType.CLASSIFICATION:
        return task_classify_document
    elif step_type == ProcessDocumentStepType.INFO_EXTRACTION:
        return task_extract_info
    else:
        raise ValueError(f"Unknown step type {step_type}")


def cancel_batch(batch_id: str):
    with atomic():
        batch = ProcessDocumentBatch.objects.get(id=batch_id)
        batch.status = ProcessingStatus.CANCELLED
        batch.save()
        ProcessDocumentJob.objects.filter(batch=batch).filter(status=ProcessingStatus.PENDING).update(status=ProcessingStatus.CANCELLED)
        ProcessDocumentStep.objects.filter(job__batch=batch).filter(status=ProcessingStatus.PENDING).update(status=ProcessingStatus.CANCELLED)
