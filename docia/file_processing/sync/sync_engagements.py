import logging
from datetime import datetime

from django.db.transaction import atomic

from docia.documents.models import DataEngagement, EngagementScope
from docia.file_processing.sync.client import ApiEngagementActivity, SyncClient

logger = logging.getLogger(__name__)


class EngagementsSync:
    def __init__(self):
        self.client = SyncClient.from_settings()

    def sync(self, scopes: list[tuple[str, str]], start: datetime, end: datetime | None = None) -> list[str]:
        """
        Update Engagement data from external system. Returns the inserted/updated engagements.

        scopes: List of tuples (purchase_organization, purchase_group)
        """

        if not self.client.is_authenticated:
            self.client.authenticate()

        if end is None:
            end = datetime.now()

        total_synced = 0
        logger.info("Fetch engagements activity...")
        for i, t_scope in enumerate(scopes):
            purchase_organization, purchase_group = t_scope
            logger.info("Process scope %s (%s/%s)", t_scope, i, len(scopes))

            # Get data from external system
            activities = self.client.list_ej_place(start, end, purchase_organization, purchase_group)
            activities = self._remove_duplicate(activities)

            # Get or Create the scope
            scope, _created = EngagementScope.objects.get_or_create(
                purchase_organization=purchase_organization, purchase_group=purchase_group
            )

            # Create and link the related engagements
            with atomic():
                engagements = [
                    DataEngagement(num_ej=activity.num_ej, external_updated_at=activity.received_at)
                    for activity in activities
                ]
                DataEngagement.objects.bulk_create(
                    engagements,
                    batch_size=1000,
                    update_conflicts=True,
                    update_fields=["external_updated_at"],
                    unique_fields=["num_ej"],
                )
                db_ids = list(
                    DataEngagement.objects.filter(num_ej__in=[ej.num_ej for ej in engagements]).values_list(
                        "id", flat=True
                    )
                )
                scope.engagements.add(*db_ids)
            total_synced += len(engagements)
            logger.info("Sync scope %s: Success. %s engagements synced", t_scope, len(engagements))
        logger.info("Success: %s engagements synced", total_synced)
        num_ejs = [ej.num_ej for ej in engagements]
        return num_ejs

    def _remove_duplicate(self, activities: list[ApiEngagementActivity]) -> list[ApiEngagementActivity]:
        """
        Removes duplicate engagement activities based on their engagement number.

        Only the most recent activity for each unique engagement number is retained.
        """
        result = []
        num_ejs = set()
        sorted_activities = sorted(activities, key=lambda x: x.received_at, reverse=True)
        for activity in sorted_activities:
            if activity.num_ej not in num_ejs:
                num_ejs.add(activity.num_ej)
                result.append(activity)
        return result
