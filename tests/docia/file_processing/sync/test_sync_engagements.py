from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from docia.documents.models import DataEngagement
from docia.file_processing.sync.sync_engagements import EngagementsSync
from tests.factories.data import DataEngagementFactory, EngagementScopeFactory
from tests.factories.file_processing import ApiEngagementActivityFactory
from tests.utils import bind_arguments


@pytest.fixture
def syncer():
    syncer = EngagementsSync()
    syncer.client.is_authenticated = True
    yield syncer


@pytest.mark.django_db
def test_sync(syncer):
    """Test that syncing handles correctly multiple scopes sync

    This test verifies that:
    1. New engagements are created from API activities
    2. Each engagement has the correct scope (purchase_organization and purchase_group)
    3. The external_updated_at field is set to the received_at timestamp from the API
    """

    api_activities = [
        ApiEngagementActivityFactory(purchase_organization="oa1", purchase_group="ga1"),
        ApiEngagementActivityFactory(purchase_organization="oa1", purchase_group="ga1"),
        ApiEngagementActivityFactory(purchase_organization="oa1", purchase_group="ga2"),
        ApiEngagementActivityFactory(purchase_organization="oa1", purchase_group="ga2"),
        ApiEngagementActivityFactory(purchase_organization="oa2", purchase_group="ga3"),
        ApiEngagementActivityFactory(purchase_organization="oa2", purchase_group="ga3"),
    ]

    # Mock
    def m_list_ej_place(
        *args,
        **kwargs,
    ):
        bound_args = bind_arguments(syncer.client.list_ej_place, *args, **kwargs)
        purchase_organization = bound_args["purchase_organization"]
        purchase_group = bound_args["purchase_group"]
        return [
            activity
            for activity in api_activities
            if activity.purchase_organization == purchase_organization and activity.purchase_group == purchase_group
        ]

    # Function call
    with patch.object(syncer.client, "list_ej_place", autospec=True, side_effect=m_list_ej_place):
        synced_num_ejs = syncer.sync([("oa1", "ga1"), ("oa1", "ga2"), ("oa2", "ga3")], start=datetime(2026, 3, 5))

    # Assert all num ejs are returned
    expected_synced_num_ejs = [activity.num_ej for activity in api_activities]
    assert sorted(synced_num_ejs) == sorted(expected_synced_num_ejs)

    # Asserts the EJ and scope are inserted
    inserted = sorted(
        list(
            DataEngagement.objects.order_by("num_ej").values(
                "num_ej",
                "external_updated_at",
                "scopes__purchase_organization",
                "scopes__purchase_group",
            )
        ),
        key=lambda x: x["num_ej"],
    )
    expected = sorted(
        [
            {
                "external_updated_at": activity.received_at,
                "num_ej": activity.num_ej,
                "scopes__purchase_organization": activity.purchase_organization,
                "scopes__purchase_group": activity.purchase_group,
            }
            for activity in api_activities
        ],
        key=lambda x: x["num_ej"],
    )
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
    ej_initial_updated_at = ej.updated_at
    scope = EngagementScopeFactory()
    ej.scopes.add(scope)

    # Same EJ, different scope, received_at later
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
        synced_num_ejs = syncer.sync([("oa", "ga")], start=datetime(2026, 3, 5))

    # Assert all num ejs are returned
    expected_synced_num_ejs = [activity.num_ej for activity in api_activities]
    assert sorted(synced_num_ejs) == sorted(expected_synced_num_ejs)

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

    # Assert updated_at is updated
    ej.refresh_from_db()
    assert ej.updated_at > ej_initial_updated_at


@pytest.mark.django_db
def test_sync_preserve_newer_external_updated_at(syncer):
    """Test that syncing preserves the newer external_updated_at when API has older data.

    This test verifies that:
    1. When an existing engagement has a newer external_updated_at than the API activity
    2. The newer date is preserved (not overwritten by the older API date)
    3. The engagement still gets the new scope added
    """

    # Existing EJ with newer external_updated_at
    num_ej = "1234567890"
    newer_date = datetime(2026, 4, 1, tzinfo=timezone.utc)
    ej = DataEngagementFactory(num_ej=num_ej, external_updated_at=newer_date)
    ej_initial_updated_at = ej.updated_at
    scope = EngagementScopeFactory()
    ej.scopes.add(scope)

    # Same EJ, but with older date from API
    older_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    api_activity = ApiEngagementActivityFactory(
        num_ej=num_ej,
        purchase_organization="oa",
        purchase_group="ga",
        received_at=older_date,
    )
    api_activities = [api_activity]

    # Function call
    with patch.object(syncer.client, "list_ej_place", autospec=True) as m_list:
        m_list.return_value = api_activities
        synced_num_ejs = syncer.sync([("oa", "ga")], start=datetime(2026, 3, 5))

    # Assert all num ejs are returned
    expected_synced_num_ejs = [activity.num_ej for activity in api_activities]
    assert sorted(synced_num_ejs) == sorted(expected_synced_num_ejs)

    # Assert that the newer external_updated_at is preserved
    updated_ej = DataEngagement.objects.get(num_ej=num_ej)
    assert updated_ej.external_updated_at == newer_date

    # Assert that the new scope was still added
    assert updated_ej.scopes.count() == 2
    assert updated_ej.scopes.filter(purchase_organization="oa", purchase_group="ga").exists()

    # Assert updated_at is preserved (no update has been performed since date is older)
    assert updated_ej.updated_at == ej_initial_updated_at


@pytest.mark.django_db
def test_sync_handles_duplicate_engagements(syncer):
    """Test that sync handles correctly duplicate engagements from the API.

    This test verifies that:
    1. When the API returns duplicate engagements (same num_ej) with different scopes
    2. Only one engagement is created in the database (with the newest timestamp)
    3. The engagement is linked to both scopes
    4. Older activities with the same num_ej are ignored
    """

    num_ej = "1234567890"

    # Create API activities with duplicate num_ej, different timestamps and scopes
    # Pattern: older, newer, older, older
    older_activity = ApiEngagementActivityFactory(
        num_ej=num_ej,
        purchase_organization="oa1",
        purchase_group="ga1",
        received_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer_activity = ApiEngagementActivityFactory(
        num_ej=num_ej,
        purchase_organization="oa1",
        purchase_group="ga1",
        received_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    newer_activity_different_scope = ApiEngagementActivityFactory(
        num_ej=num_ej,
        purchase_organization="oa2",
        purchase_group="ga2",
        received_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    api_activities = [
        older_activity,
        newer_activity,
        older_activity,
        newer_activity_different_scope,
        older_activity,
    ]

    # Mock the API to return different activities for different scopes
    def m_list_ej_place(*args, **kwargs):
        bound_args = bind_arguments(syncer.client.list_ej_place, *args, **kwargs)
        purchase_organization = bound_args["purchase_organization"]
        purchase_group = bound_args["purchase_group"]

        return [
            activity
            for activity in api_activities
            if activity.purchase_organization == purchase_organization and activity.purchase_group == purchase_group
        ]

    # Function call - sync both scopes
    with patch.object(syncer.client, "list_ej_place", autospec=True, side_effect=m_list_ej_place):
        synced_num_ejs = syncer.sync([("oa1", "ga1"), ("oa2", "ga2")], start=datetime(2026, 1, 1))

    # Assert only one num_ej is returned (no duplicates)
    expected_synced_num_ejs = [num_ej]
    assert synced_num_ejs == expected_synced_num_ejs

    # Assert the engagement has the newest timestamp
    created = list(DataEngagement.objects.values_list("num_ej", "external_updated_at"))
    assert created == [(num_ej, newer_activity.received_at)]

    # Assert the engagement is linked to all scopes (both oa1/ga2 and oa2/ga2)
    created_ej = DataEngagement.objects.get()
    created_scopes = sorted(list(created_ej.scopes.values_list("purchase_organization", "purchase_group")))
    expected_scopes = [("oa1", "ga1"), ("oa2", "ga2")]
    assert created_scopes == expected_scopes
