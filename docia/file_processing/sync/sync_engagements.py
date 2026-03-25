import logging
from datetime import datetime

from django.db.transaction import atomic
from django.utils import timezone

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

        num_ejs_synced = set()
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
            num_ejs = self._save_engagements(activities, scope)
            num_ejs_synced.update(num_ejs)
            logger.info("Sync scope %s: Success. %s engagements synced", t_scope, len(num_ejs))
        logger.info("Success: %s engagements synced", len(num_ejs_synced))
        return sorted(num_ejs_synced)

    def _save_engagements(self, activities: list[ApiEngagementActivity], scope: EngagementScope) -> list[str]:
        """
        Save engagements with the latest external_updated_at dates and link them to scope.

        Args:
            activities: List of API engagement activities
            scope: The engagement scope to link engagements to

        Returns:
            List of num_ejs for the saved engagements
        """
        with atomic():
            engagements_to_add = []
            engagements_to_update = []

            # Fetch existing engagements with their current dates for comparison
            existing_engagements_dict = {
                ej.num_ej: ej
                for ej in DataEngagement.objects.filter(num_ej__in=[activity.num_ej for activity in activities])
            }

            for activity in activities:
                existing_engagement = existing_engagements_dict.get(activity.num_ej)
                if existing_engagement:
                    # Only update if the new date is newer
                    if activity.received_at > existing_engagement.external_updated_at:
                        existing_engagement.external_updated_at = activity.received_at
                        existing_engagement.updated_at = timezone.now()
                        engagements_to_update.append(existing_engagement)
                else:
                    # Engagements to add
                    engagements_to_add.append(
                        DataEngagement(num_ej=activity.num_ej, external_updated_at=activity.received_at)
                    )

            # Bulk create engagements to add
            if engagements_to_add:
                DataEngagement.objects.bulk_create(engagements_to_add, batch_size=1000)

            # Bulk update existing engagements that need updating
            if engagements_to_update:
                DataEngagement.objects.bulk_update(
                    engagements_to_update, fields=["external_updated_at", "updated_at"], batch_size=1000
                )

            # Link all engagements to the scope
            num_ejs = [activity.num_ej for activity in activities]
            db_ids = list(DataEngagement.objects.filter(num_ej__in=num_ejs).values_list("id", flat=True))
            scope.engagements.add(*db_ids)

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
