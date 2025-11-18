from django.db import models

from docia.common.models import BaseModel


class JobStatus(models.TextChoices):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class JobName(models.TextChoices):
    TEXT_EXTRACTION = "TEXT_EXTRACTION"
    CLASSIFICATION = "CLASSIFICATION"
    ANALYZE = "ANALYZE"


class BatchJob(BaseModel):
    job_name = models.CharField(choices=JobName.choices)
    folder = models.CharField(max_length=50)
    status = models.CharField(choices=JobStatus.choices)
    celery_task_id = models.CharField(max_length=250, blank=True)


class DocumentJob(BaseModel):
    job_name = models.CharField(choices=JobName.choices)
    batch = models.ForeignKey(BatchJob, on_delete=models.CASCADE, null=True)
    document = models.ForeignKey("docia.DataAttachment", on_delete=models.CASCADE)
    status = models.CharField(choices=JobStatus.choices)
    error = models.CharField(default="", blank=True)
    traceback = models.TextField(default="", blank=True)
    celery_task_id = models.CharField(max_length=250, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
