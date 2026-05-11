import logging
from datetime import datetime

from django.db.transaction import atomic
from django.utils import timezone

from docia.documents.models import Engagement, EngagementScope
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
            purchase_organization, s_purchase_groups = t_scope
            logger.info("Process scope %s (%s/%s)", t_scope, i, len(scopes))

            # Get data from external system
            activities = self.client.list_ej_place(start, end, purchase_organization)
            if s_purchase_groups != "*":
                purchase_groups = s_purchase_groups.split("-")
                activities = [a for a in activities if a.purchase_group in purchase_groups]
            activities = self._remove_duplicate(activities)

            num_ejs = self._save_scopes_and_engagements(activities)
            num_ejs_synced.update(num_ejs)
            logger.info("Sync scope %s: Success. %s engagements synced", t_scope, len(num_ejs))
        logger.info("Success: %s engagements synced", len(num_ejs_synced))
        return sorted(num_ejs_synced)

    def _save_scopes_and_engagements(self, activities: list[ApiEngagementActivity]) -> list[str]:
        scopes = self._save_scopes(activities)
        num_ejs = set()
        for scope in scopes:
            scope_activities = [
                a
                for a in activities
                if a.purchase_organization == scope.purchase_organization and a.purchase_group == scope.purchase_group
            ]
            num_ejs.update(self._save_engagements(scope_activities, scope))
        return sorted(num_ejs)

    def _save_scopes(self, activities: list[ApiEngagementActivity]) -> list[EngagementScope]:
        t_scopes = set((a.purchase_organization, a.purchase_group) for a in activities)
        scopes = []
        for org, group in t_scopes:
            scope, _ = EngagementScope.objects.get_or_create(
                purchase_organization=org,
                purchase_group=group,
            )
            scopes.append(scope)
        return scopes

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
                for ej in Engagement.objects.filter(num_ej__in=[activity.num_ej for activity in activities])
            }

            for activity in activities:
                existing_engagement = existing_engagements_dict.get(activity.num_ej)
                if existing_engagement:
                    # Only update if the new date is newer
                    if (
                        not existing_engagement.external_updated_at
                        or activity.received_at > existing_engagement.external_updated_at
                    ):
                        existing_engagement.external_updated_at = activity.received_at
                        existing_engagement.updated_at = timezone.now()
                        engagements_to_update.append(existing_engagement)
                else:
                    # Engagements to add
                    engagements_to_add.append(
                        Engagement(num_ej=activity.num_ej, external_updated_at=activity.received_at)
                    )

            # Bulk create engagements to add
            if engagements_to_add:
                Engagement.objects.bulk_create(engagements_to_add, batch_size=1000)

            # Bulk update existing engagements that need updating
            if engagements_to_update:
                Engagement.objects.bulk_update(
                    engagements_to_update, fields=["external_updated_at", "updated_at"], batch_size=1000
                )

            # Link all engagements to the scope
            num_ejs = [activity.num_ej for activity in activities]
            db_ids = list(Engagement.objects.filter(num_ej__in=num_ejs).values_list("id", flat=True))
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
