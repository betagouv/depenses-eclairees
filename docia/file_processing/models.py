from django.contrib.postgres.fields import ArrayField
from django.db import models

from docia.common.models import BaseModel


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


class ProcessDocumentBatch(BaseModel):
    folder = models.CharField(max_length=100, null=True, blank=True)  # noqa: DJ001
    target_classifications = ArrayField(models.CharField(max_length=255), null=True, blank=True)
    status = models.CharField(choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING)
    celery_task_id = models.CharField(max_length=250, blank=True)

    def __str__(self):
        return f"{self.folder} {self.status}"


class ProcessDocumentJob(BaseModel):
    batch = models.ForeignKey(
        ProcessDocumentBatch, on_delete=models.CASCADE, related_name="job_set", related_query_name="job"
    )
    document = models.ForeignKey("docia.DataAttachment", on_delete=models.CASCADE)
    status = models.CharField(choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING)
    celery_task_id = models.CharField(max_length=250, blank=True)

    def __str__(self):
        return f"{self.status}"


class ProcessDocumentStep(BaseModel):
    job = models.ForeignKey(
        ProcessDocumentJob, on_delete=models.CASCADE, related_name="step_set", related_query_name="step"
    )
    step_type = models.CharField(choices=ProcessDocumentStepType.choices)
    status = models.CharField(choices=ProcessingStatus.choices)
    error = models.CharField(default="", blank=True)
    traceback = models.TextField(default="", blank=True)
    celery_task_id = models.CharField(max_length=250, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

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
