import logging
import time
import traceback
import uuid
from abc import ABC
import datetime

from django.db.models import Count
from django.db.transaction import atomic

from celery import chord, shared_task
from tqdm import tqdm

from ..models import DataAttachment
from .models import BatchJob, DocumentJob, JobName, JobStatus

logger = logging.getLogger(__name__)


class AbstractJobWorker(ABC):
    def run(self, job_id: str) -> JobStatus:
        with atomic():
            job = DocumentJob.objects.select_for_update(nowait=True).get(id=job_id)

            if job.status != JobStatus.PENDING:
                logger.info(f"Workload {job_id} ({job.document.file.name}) already processed")
                return

            job.started_at = datetime.datetime.now(tz=datetime.timezone.utc)

            document = job.document
            file_path = document.file.name

            try:
                self.process(job)
            except Exception as e:
                logger.exception("(%s) Error during processing %s", self.__class__.__name__, file_path)
                job.status = JobStatus.FAILURE
                job.error = str(e)
                job.traceback = traceback.format_exc()
            else:
                job.status = JobStatus.SUCCESS

            job.finished_at = datetime.datetime.now(tz=datetime.timezone.utc)
            job.duration = job.finished_at - job.started_at
            job.save()

        return job.status

    def process(self, job): ...


@shared_task
def task_finalize_batch(job_results: list[JobStatus], batch_id: str) -> JobStatus:
    """
    Celery task to finalize a batch text extraction process.
    Set the status to either SUCCESS or FAILURE based on the status of all tasks in the batch.

    Args:
        batch_id (str): The ID of the BatchTextExtraction to finalize

    Returns:
        JobStatus: The final status of the batch text extraction task
    """
    with atomic():
        batch = BatchJob.objects.select_for_update(nowait=True).get(id=batch_id)

        if batch.documentjob_set.filter(status__in=(JobStatus.PENDING, JobStatus.STARTED)).exists():
            logger.error(f"Batch {batch_id} not finished yet")
            raise ValueError(f"Batch not finished yet. (batch_id={batch.id})")
        elif batch.documentjob_set.filter(status=JobStatus.FAILURE).exists():
            batch.status = JobStatus.FAILURE
        else:
            batch.status = JobStatus.SUCCESS

        batch.save()

    return batch.status


def launch_batch(job_name: JobName, folder: str, doc_task):
    with atomic():
        batch = BatchJob.objects.create(
            job_name=job_name,
            folder=folder,
            status=JobStatus.STARTED,
            celery_task_id=str(uuid.uuid4()),
        )
        subjobs = []
        subtasks = []
        for document in DataAttachment.objects.filter(file__startswith=folder):
            job = DocumentJob(
                job_name=JobName.CLASSIFICATION,
                batch=batch,
                document=document,
                status=JobStatus.PENDING,
                celery_task_id=str(uuid.uuid4()),
            )
            subjobs.append(job)
            subtasks.append(doc_task.s(job.id).set(task_id=job.celery_task_id))
        batch.documentjob_set.bulk_create(subjobs)
    r = chord(subtasks)(task_finalize_batch.s(batch.id).set(task_id=batch.celery_task_id))
    return batch, r


def launch_document_job(job_name: JobName, document: DataAttachment, doc_task):
    job = DocumentJob.objects.create(
        job_name=job_name,
        document=document,
        status=JobStatus.PENDING,
        celery_task_id=str(uuid.uuid4()),
    )
    r = doc_task.apply_async(
        args=(job.id,),
        task_id=job.celery_task_id,
    )
    return job, r


def get_batch_progress(batch_id: str):
    batch = BatchJob.objects.get(id=batch_id)
    # Count the number of tasks in each status
    qs_aggregate = batch.documentjob_set.values("status").annotate(count=Count("id"))
    counters = dict((row["status"], row["count"]) for row in qs_aggregate)
    completed = sum(
        tasks_count for status, tasks_count in counters.items() if status in [JobStatus.SUCCESS, JobStatus.FAILURE]
    )
    errors = counters.get(JobStatus.FAILURE, 0)
    total = sum(tasks_count for tasks_count in counters.values())
    return {
        "status": batch.status,
        "completed": completed,
        "errors": errors,
        "total": total,
    }


def display_batch_progress(batch_id: str):
    batch = BatchJob.objects.get(id=batch_id)
    total_tasks = batch.documentjob_set.count()
    logger.info(
        "Processing batch %(batch_id)s (folder=%(folder)s, tasks=%(total_tasks)s)...",
        dict(
            batch_id=batch.id,
            folder=batch.folder,
            total_tasks=total_tasks,
        ),
    )
    with tqdm(total=total_tasks) as pbar:
        while True:
            progress = get_batch_progress(batch_id)
            pbar.n = progress["completed"]
            pbar.set_postfix(errors=progress["errors"])
            if progress["status"] in [JobStatus.SUCCESS, JobStatus.FAILURE]:
                break
            time.sleep(1)
    logger.info("Completed")
