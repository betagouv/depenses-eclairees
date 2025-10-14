from django.contrib.auth import get_user_model
from django.db import models

from docia.common.models import BaseModel


class TrackingEvent(BaseModel):
    category = models.CharField(max_length=255)
    action = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    # Page where the event occurred
    page_url = models.CharField(default="", blank=True, help_text="URL path or component identifier")

    # User agent information
    user_agent = models.TextField(default="", blank=True, help_text="User's browser and device information")

    # Link to the user
    user = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    num_ej = models.CharField(max_length=20, default="", blank=True)

    def __str__(self):
        return f"{self.category} - {self.action} - {self.name}"
