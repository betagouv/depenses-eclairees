import datetime
import logging
import time
import traceback
from abc import ABC

from django.db.models import Count
from django.db.transaction import atomic

from celery.result import GroupResult
from tqdm.autonotebook import tqdm

from .models import ProcessDocumentBatch, ProcessDocumentStep, ProcessDocumentStepType, ProcessingStatus

logger = logging.getLogger(__name__)


class AbstractStepRunner(ABC):
    def run(self, step_id: str) -> ProcessingStatus:
        with atomic():
            step = ProcessDocumentStep.objects.select_related("job").select_for_update(nowait=True).get(id=step_id)

            file_path = step.job.document.file.name

            if step.status != ProcessingStatus.PENDING:
                logger.info(f"Step already processed step={step_id} ({file_path}) status={step.status}")
                return

            if step.job.status == ProcessingStatus.CANCELLED:
                logger.info(f"Job cancelled job={step.job.id} step={step_id} ({file_path})")
                return

            if step.job.status not in (ProcessingStatus.PENDING, ProcessingStatus.STARTED):
                logger.info(
                    f"Job already processed job={step.job.id} step={step_id} ({file_path}) status={step.job.status}"
                )
                return

            if step.job.status == ProcessingStatus.PENDING:
                step.job.status = ProcessingStatus.STARTED
                step.job.save(update_fields=["status"])

            step.started_at = datetime.datetime.now(tz=datetime.timezone.utc)
            step.status = ProcessingStatus.STARTED
            step.save(update_fields=["status"])
            step.job.status = ProcessingStatus.STARTED

        try:
            self.process(step)
        except Exception as e:
            logger.exception("(%s) Error during processing %s", self.__class__.__name__, file_path)
            step.status = ProcessingStatus.FAILURE
            step.error = str(e)
            step.traceback = traceback.format_exc()
        else:
            step.status = ProcessingStatus.SUCCESS

        step.finished_at = datetime.datetime.now(tz=datetime.timezone.utc)
        step.duration = step.finished_at - step.started_at
        step.save()

        # Propagate failure
        if step.status == ProcessingStatus.FAILURE:
            step.job.status = ProcessingStatus.FAILURE
            step.job.save(update_fields=["status"])

            # Skip next steps
            step.job.step_set.filter(status=ProcessingStatus.PENDING).update(status=ProcessingStatus.SKIPPED)

        # Finish job if needed
        if not step.job.step_set.filter(status__in=[ProcessingStatus.PENDING, ProcessingStatus.STARTED]).exists():
            if step.job.step_set.filter(status=ProcessingStatus.FAILURE).exists():
                step.job.status = ProcessingStatus.FAILURE
            else:
                step.job.status = ProcessingStatus.SUCCESS
            step.job.save(update_fields=["status"])

            # Finish batch if needed
            if not step.job.batch.job_set.filter(
                status__in=[ProcessingStatus.PENDING, ProcessingStatus.STARTED]
            ).exists():
                if step.job.batch.job_set.filter(status=ProcessingStatus.FAILURE).exists():
                    step.job.batch.status = ProcessingStatus.FAILURE
                else:
                    step.job.batch.status = ProcessingStatus.SUCCESS
                step.job.batch.save(update_fields=["status"])

        return step.status

    def process(self, step: ProcessDocumentStep): ...


def get_batch_progress_per_step(batch):
    step_counters = {}
    for step_type in [
        ProcessDocumentStepType.TEXT_EXTRACTION,
        ProcessDocumentStepType.CLASSIFICATION,
        ProcessDocumentStepType.INFO_EXTRACTION,
    ]:
        step_counters[step_type] = {
            "progress": 0,
            "errors": 0,
            "skipped": 0,
            "total": 0,
        }
    qs_aggregate = (
        ProcessDocumentStep.objects.filter(job__batch=batch).values("step_type", "status").annotate(count=Count("id"))
    )
    aggregate = list(qs_aggregate)
    step_types = set(row["step_type"] for row in aggregate)
    for step_type in step_types:
        counters = dict((row["status"], row["count"]) for row in aggregate if row["step_type"] == step_type)
        progress = sum(
            tasks_count
            for status, tasks_count in counters.items()
            if status not in [ProcessingStatus.PENDING, ProcessingStatus.STARTED]
        )
        skipped = counters.get(ProcessingStatus.SKIPPED, 0)
        errors = counters.get(ProcessingStatus.FAILURE, 0)
        total = sum(tasks_count for tasks_count in counters.values())
        step_counters[step_type] = {
            "progress": progress,
            "skipped": skipped,
            "errors": errors,
            "total": total,
        }
    return step_counters


def get_batch_progress(batch_id: str):
    batch = ProcessDocumentBatch.objects.get(id=batch_id)
    # Count the number of tasks in each status
    qs_aggregate = batch.job_set.values("status").annotate(count=Count("id"))
    counters = dict((row["status"], row["count"]) for row in qs_aggregate)
    progress = sum(
        tasks_count
        for status, tasks_count in counters.items()
        if status not in [ProcessingStatus.PENDING, ProcessingStatus.STARTED]
    )
    errors = counters.get(ProcessingStatus.FAILURE, 0)
    total = sum(tasks_count for tasks_count in counters.values())

    steps_progress = get_batch_progress_per_step(batch)

    return {
        "status": batch.status,
        "progress": progress,
        "errors": errors,
        "total": total,
        "steps": steps_progress,
    }


def display_batch_progress(batch_id: str):
    batch = ProcessDocumentBatch.objects.get(id=batch_id)
    total_jobs = batch.job_set.count()
    total_tasks = ProcessDocumentStep.objects.filter(job__batch=batch).count()
    progress = get_batch_progress(batch_id)
    logger.info(
        "Processing batch %(batch_id)s (folder=%(folder)s, jobs=%(total_jobs)s, tasks=%(total_tasks)s)...",
        dict(
            batch_id=batch.id,
            folder=batch.folder,
            total_jobs=total_jobs,
            total_tasks=total_tasks,
        ),
    )

    with (
        tqdm(desc="      documents", total=total_jobs, position=0) as pbar_jobs,
        tqdm(
            desc="            ocr", total=progress["steps"][ProcessDocumentStepType.TEXT_EXTRACTION]["total"], position=1
        ) as pbar_ocr,
        tqdm(
            desc=" classification", total=progress["steps"][ProcessDocumentStepType.CLASSIFICATION]["total"], position=2
        ) as pbar_classification,
        tqdm(
            desc="info extraction",
            total=progress["steps"][ProcessDocumentStepType.INFO_EXTRACTION]["total"],
            position=3,
        ) as pbar_info_extraction,
    ):
        while True:
            progress = get_batch_progress(batch_id)
            pbar_jobs.n = progress["progress"]
            pbar_jobs.set_postfix(errors=progress["errors"])
            pbar_ocr.n = progress["steps"][ProcessDocumentStepType.TEXT_EXTRACTION]["progress"]
            pbar_ocr.set_postfix(
                errors=progress["steps"][ProcessDocumentStepType.TEXT_EXTRACTION]["errors"],
                skipped=progress["steps"][ProcessDocumentStepType.TEXT_EXTRACTION]["skipped"],
            )
            pbar_classification.n = progress["steps"][ProcessDocumentStepType.CLASSIFICATION]["progress"]
            pbar_classification.set_postfix(
                errors=progress["steps"][ProcessDocumentStepType.CLASSIFICATION]["errors"],
                skipped=progress["steps"][ProcessDocumentStepType.CLASSIFICATION]["skipped"],
            )
            pbar_info_extraction.n = progress["steps"][ProcessDocumentStepType.INFO_EXTRACTION]["progress"]
            pbar_info_extraction.set_postfix(
                errors=progress["steps"][ProcessDocumentStepType.INFO_EXTRACTION]["errors"],
                skipped=progress["steps"][ProcessDocumentStepType.INFO_EXTRACTION]["skipped"],
            )
            if progress["status"] in [ProcessingStatus.SUCCESS, ProcessingStatus.FAILURE, ProcessingStatus.CANCELLED]:
                break
            time.sleep(1)
    logger.info("Completed")


def get_group_result_progress(celery_task_id: str):
    gr = GroupResult.restore(celery_task_id)
    # Count the number of tasks in each status
    completed = gr.completed_count()
    errors = len([res for res in gr if res.failed()])
    total = len(gr.children)
    return {
        "is_done": gr.ready(),
        "completed": completed,
        "errors": errors,
        "total": total,
    }


def display_group_progress(celery_task_id: str):
    gr = GroupResult.restore(celery_task_id)
    total_tasks = len(gr.children)
    with tqdm(total=total_tasks) as pbar:
        while True:
            progress = get_group_result_progress(celery_task_id)
            pbar.n = progress["completed"]
            pbar.set_postfix(errors=progress["errors"])
            if progress["is_done"]:
                break
            time.sleep(1)
    logger.info("Completed")
