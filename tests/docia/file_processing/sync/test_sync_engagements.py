from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from docia.documents.models import DataEngagement
from docia.file_processing.sync.sync_engagements import EngagementsSync
from tests.factories.data import DataEngagementFactory, EngagementScopeFactory
from tests.factories.file_processing import ApiEngagementActivityFactory


@pytest.fixture
def syncer():
    syncer = EngagementsSync()
    syncer.client.is_authenticated = True
    yield syncer


@pytest.mark.django_db
def test_sync(syncer):
    """Test that syncing creates new engagements with their scopes.

    This test verifies that:
    1. New engagements are created from API activities
    2. Each engagement has the correct scope (purchase_organization and purchase_group)
    3. The external_updated_at field is set to the received_at timestamp from the API
    """

    # Setup
    num_ej1 = "1234567890"
    num_ej2 = "2234567890"
    num_ej3 = "3234567890"

    def activity_factory(num_ej):
        return ApiEngagementActivityFactory(num_ej=num_ej, purchase_organization="oa", purchase_group="ga")

    api_activities = [
        activity_factory(num_ej=num_ej1),
        activity_factory(num_ej=num_ej2),
        activity_factory(num_ej=num_ej3),
    ]

    # Function call
    with patch.object(syncer.client, "list_ej_place", autospec=True) as m_list:
        m_list.return_value = api_activities
        syncer.sync([("oa", "ga")], start=datetime(2026, 3, 5))

    # Asserts the EJ and scope are inserted
    inserted = list(
        DataEngagement.objects.order_by("num_ej").values(
            "num_ej",
            "external_updated_at",
            "scopes__purchase_organization",
            "scopes__purchase_group",
        )
    )
    expected = [
        {
            "external_updated_at": activity.received_at,
            "num_ej": activity.num_ej,
            "scopes__purchase_organization": "oa",
            "scopes__purchase_group": "ga",
        }
        for activity in api_activities
    ]
    assert inserted == expected


@pytest.mark.django_db
def test_sync_update_ej(syncer):
    """Test that syncing updates an existing engagement with a new scope.

    This test verifies that:
    1. An existing engagement is not duplicated when syncing with new data
    2. The previous scope of the engagement is preserved
    3. The new scope from the API activity is added to the engagement
    4. The external_updated_at field is updated to the received_at timestamp from the API
    """

    # Existing EJ with existing scope
    num_ej = "1234567890"
    ej = DataEngagementFactory(num_ej=num_ej, external_updated_at=datetime(2026, 1, 7))
    scope = EngagementScopeFactory()
    ej.scopes.add(scope)

    # Same EJ, different scope
    api_activity = ApiEngagementActivityFactory(
        num_ej=num_ej,
        purchase_organization="oa",
        purchase_group="ga",
        received_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
    )
    api_activities = [api_activity]

    # Function call
    with patch.object(syncer.client, "list_ej_place", autospec=True) as m_list:
        m_list.return_value = api_activities
        syncer.sync([("oa", "ga")], start=datetime(2026, 3, 5))

    # Asserts :
    #   - the EJ is not duplicated
    #   - the previous scope is kept
    #   - the new scope is added
    inserted = list(
        DataEngagement.objects.order_by("scopes__created_at").values(
            "id",
            "num_ej",
            "external_updated_at",
            "scopes__purchase_organization",
            "scopes__purchase_group",
        )
    )
    expected = [
        {
            "id": ej.id,
            "external_updated_at": api_activity.received_at,
            "num_ej": ej.num_ej,
            "scopes__purchase_organization": scope.purchase_organization,
            "scopes__purchase_group": scope.purchase_group,
        },
        {
            "id": ej.id,
            "external_updated_at": api_activity.received_at,
            "num_ej": ej.num_ej,
            "scopes__purchase_organization": "oa",
            "scopes__purchase_group": "ga",
        },
    ]
    assert inserted == expected
