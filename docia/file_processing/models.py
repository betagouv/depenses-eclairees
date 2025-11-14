from django.db import models

from docia.common.models import BaseModel


class TaskStatus(models.TextChoices):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class BatchTextExtraction(BaseModel):
    folder = models.CharField(max_length=50)
    status = models.CharField(choices=TaskStatus.choices)


class FileTextExtraction(BaseModel):
    batch = models.ForeignKey(BatchTextExtraction, on_delete=models.CASCADE, null=True)
    document = models.ForeignKey("docia.DataAttachment", on_delete=models.CASCADE)
    status = models.CharField(choices=TaskStatus.choices)
    error = models.TextField(default="", blank=True)
