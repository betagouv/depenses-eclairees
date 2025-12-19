from django.db import models


class RateGateState(models.Model):
    key = models.CharField(max_length=200, primary_key=True)
    next_allowed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.key} (next: {self.next_allowed_at})"
