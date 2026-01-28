from django.contrib.auth.models import Group
from django.db import models

from docia.common.models import BaseModel
from docia.documents.models import EngagementScope


class ScopeGroupPermission(BaseModel):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
    )
    scope = models.ForeignKey(
        EngagementScope,
        on_delete=models.CASCADE,
    )
