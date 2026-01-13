import datetime
import logging
import traceback
from abc import ABC

from django.db.transaction import atomic

from docia.file_processing.models import ProcessDocumentStep, ProcessingStatus
from docia.file_processing.pipeline.steps.exceptions import SkipStepException

logger = logging.getLogger(__name__)


class AbstractStepRunner(ABC):
    def run(self, step_id: str) -> ProcessingStatus:
        with atomic():
            step = ProcessDocumentStep.objects.select_related("job").select_for_update(nowait=True).get(id=step_id)

            file_path = step.job.document.file.name

            if step.status != ProcessingStatus.PENDING:
                logger.info(f"Step already processed step={step_id} ({file_path}) status={step.status}")
                return step.status

            if step.job.status == ProcessingStatus.CANCELLED:
                logger.info(f"Job cancelled job={step.job.id} step={step_id} ({file_path})")
                return step.status

            if step.job.status not in (ProcessingStatus.PENDING, ProcessingStatus.STARTED):
                logger.info(
                    f"Job already processed job={step.job.id} step={step_id} ({file_path}) status={step.job.status}"
                )
                return step.status

            if step.job.status == ProcessingStatus.PENDING:
                step.job.status = ProcessingStatus.STARTED
                step.job.save(update_fields=["status"])

            step.started_at = datetime.datetime.now(tz=datetime.timezone.utc)
            step.status = ProcessingStatus.STARTED
            step.save(update_fields=["status"])
            step.job.status = ProcessingStatus.STARTED

        try:
            self.process(step)
        except SkipStepException as e:
            logger.info("(%s) Skip %s: %s", self.__class__.__name__, file_path, e)
            step.status = ProcessingStatus.SKIPPED
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

        # Propagate failure and skip
        if step.status in (ProcessingStatus.FAILURE, ProcessingStatus.SKIPPED):
            step.job.status = step.status
            step.job.save(update_fields=["status"])

            # Skip next steps
            step.job.step_set.filter(status=ProcessingStatus.PENDING).update(status=ProcessingStatus.SKIPPED)

        # Finish job if needed
        if not step.job.step_set.filter(status__in=[ProcessingStatus.PENDING, ProcessingStatus.STARTED]).exists():
            # If job has not already ended
            if step.job.status == ProcessingStatus.STARTED:
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
