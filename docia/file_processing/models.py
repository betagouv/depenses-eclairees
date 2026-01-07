from datetime import timedelta

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Max, OuterRef, Subquery
from django.utils import timezone

from docia.common.models import BaseModel

from .rategate.models import RateGateState  # noqa: F401


class ProcessingStatus(models.TextChoices):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class ProcessDocumentStepType(models.TextChoices):
    TEXT_EXTRACTION = "TEXT_EXTRACTION"
    CLASSIFICATION = "CLASSIFICATION"
    INFO_EXTRACTION = "INFO_EXTRACTION"


BATCH_STUCK_TIMEOUT = 30 * 60  # 30min (in seconds)


class ProcessDocumentBatchQuerySet(models.QuerySet):
    def filter_stuck_batches(self, timeout_seconds: int = BATCH_STUCK_TIMEOUT):
        """Look for stuck batches which last update was more than timeout_seconds ago."""

        # Get the latest finished_at timestamp from any job step for each batch
        latest_step = (
            ProcessDocumentStep.objects.filter(job__batch=OuterRef("pk"))
            .annotate(latest_finished_at=Max("finished_at"))
            .values("latest_finished_at")
        )

        # Filter batches with no recent step updates
        timeout_threshold = timezone.now() - timedelta(seconds=timeout_seconds)
        stuck_batches = (
            self.filter(status__in=(ProcessingStatus.STARTED, ProcessingStatus.PENDING))
            .annotate(last_job_step_finished_at=Subquery(latest_step))
            .filter(last_job_step_finished_at__lt=timeout_threshold)
        )

        return stuck_batches


class ProcessDocumentBatchManager(models.Manager.from_queryset(ProcessDocumentBatchQuerySet)):
    pass


class ProcessDocumentBatch(BaseModel):
    folder = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001
    target_classifications = ArrayField(models.CharField(max_length=255), null=True, blank=True)
    steps = ArrayField(models.CharField(max_length=255, choices=ProcessDocumentStepType.choices))
    status = models.CharField(choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING)
    celery_task_id = models.CharField(max_length=250, blank=True)
    retry_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True)

    objects = ProcessDocumentBatchManager()

    def __str__(self):
        return f"{self.folder} {self.status}"


class ProcessDocumentJob(BaseModel):
    batch = models.ForeignKey(
        ProcessDocumentBatch, on_delete=models.CASCADE, related_name="job_set", related_query_name="job"
    )
    document = models.ForeignKey("docia.Document", on_delete=models.CASCADE)
    status = models.CharField(choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING)
    celery_task_id = models.CharField(max_length=250, blank=True)

    def __str__(self):
        return f"{self.status}"


class ProcessDocumentStep(BaseModel):
    job = models.ForeignKey(
        ProcessDocumentJob, on_delete=models.CASCADE, related_name="step_set", related_query_name="step"
    )
    step_type = models.CharField(choices=ProcessDocumentStepType.choices)
    order = models.PositiveIntegerField()
    status = models.CharField(choices=ProcessingStatus.choices)
    error = models.CharField(default="", blank=True)
    traceback = models.TextField(default="", blank=True)
    celery_task_id = models.CharField(max_length=250, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    def get_next(self) -> "ProcessDocumentStep | None":
        return self.job.step_set.filter(order__gt=self.order).order_by("order").first()

    def __str__(self):
        return f"{self.step_type} - {self.status}"


class FileInfo(BaseModel):
    file = models.FileField(null=True, blank=True, max_length=1000, unique=True)
    filename = models.CharField(max_length=1000)
    folder = models.CharField()
    num_ej = models.CharField(max_length=20)
    extension = models.CharField(max_length=10)
    size = models.PositiveIntegerField()
    hash = models.CharField()
    created_date = models.DateField()
