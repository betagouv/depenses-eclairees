from django.contrib.auth.models import Group
from django.db import models

from docia.common.models import BaseModel


class GroupScope(BaseModel):
    group = models.ForeignKey(
        Group,
        related_name="scope_set",
        related_query_name="scope",
        on_delete=models.CASCADE,
    )
    purchase_organization = models.CharField(max_length=255)
    purchase_group = models.CharField(max_length=255)

    class Meta:
        unique_together = [("group", "purchase_organization", "purchase_group")]
        verbose_name = "Périmètre de groupe"
        verbose_name_plural = "Périmètres de group"

    def __str__(self):
        return f"{self.purchase_organization}/{self.purchase_group}"
