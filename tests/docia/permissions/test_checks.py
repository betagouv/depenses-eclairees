from django.contrib.auth.models import Permission

import pytest

from docia.permissions.checks import get_user_allowed_ej_qs, user_can_view_ej
from tests.factories.data import DataEngagementFactory, EngagementScopeFactory
from tests.factories.users import GroupFactory, UserFactory
from tests.utils import assert_queryset_equal


class TestGetUserAllowedEj:
    @pytest.mark.django_db
    def test_empty(self):
        """Test that get_user_allowed_ej_qs returns empty queryset for user with no scopes."""
        user = UserFactory()
        result = get_user_allowed_ej_qs(user)
        assert_queryset_equal(result, [], ordered=False)

    @pytest.mark.django_db
    def test_with_scopes(self):
        """Test that get_user_allowed_ej_qs returns correct engagements for user with scopes."""
        user = UserFactory()
        group = GroupFactory()
        group.user_set.add(user)

        # Create engagements and scopes
        ej1, ej2, ej3, _ej4 = DataEngagementFactory.create_batch(4)

        scope1 = EngagementScopeFactory(name="scope1")
        scope1.engagements.add(ej1, ej2)
        scope1.groups.add(group)

        # scope2 is not linked to the group
        scope2 = EngagementScopeFactory(name="scope2")
        scope2.engagements.add(ej3)

        result = get_user_allowed_ej_qs(user)
        # Only ej 1 & 2 should be returned, 3 is not in the same scope, and 4 has no scope
        assert_queryset_equal(result, [ej1, ej2], ordered=False)

    @pytest.mark.django_db
    def test_multiple_groups(self):
        """Test that get_user_allowed_ej_qs works with multiple groups."""
        user = UserFactory()
        group1 = GroupFactory()
        group2 = GroupFactory()
        group1.user_set.add(user)
        group2.user_set.add(user)

        # Create engagements and scopes
        ej1 = DataEngagementFactory(num_ej="EJ001")
        ej2 = DataEngagementFactory(num_ej="EJ002")
        ej3 = DataEngagementFactory(num_ej="EJ003")

        scope1 = EngagementScopeFactory(name="scope1")
        scope1.engagements.add(ej1)
        scope1.groups.add(group1)

        scope2 = EngagementScopeFactory(name="scope2")
        scope2.engagements.add(ej2, ej3)
        scope2.groups.add(group2)

        result = get_user_allowed_ej_qs(user)
        assert_queryset_equal(result, [ej1, ej2, ej3], ordered=False)

    @pytest.mark.django_db
    def test_distinct_results(self):
        """Test that get_user_allowed_ej_qs returns distinct results when EJ appears in multiple scopes."""
        user = UserFactory()
        group = GroupFactory()
        group.user_set.add(user)

        ej1 = DataEngagementFactory(num_ej="EJ001")
        ej2 = DataEngagementFactory(num_ej="EJ002")

        # Create two scopes that both include ej1
        scope1 = EngagementScopeFactory(name="scope1")
        scope1.engagements.add(ej1, ej2)
        scope1.groups.add(group)

        scope2 = EngagementScopeFactory(name="scope2")
        scope2.engagements.add(ej1)  # ej1 appears in both scopes
        scope2.groups.add(group)

        result = get_user_allowed_ej_qs(user)
        # Should return 2 distinct EJs, not 3 (even though ej1 appears in 2 scopes)
        assert_queryset_equal(result, [ej1, ej2], ordered=False)


class TestUserCanViewEj:
    def _add_permission(self, user):
        group = GroupFactory()
        group.user_set.add(user)
        permission = Permission.objects.get(codename="view_document", content_type__app_label="docia")
        group.permissions.add(permission)

    def _add_scope(self, user, ej):
        group = GroupFactory()
        group.user_set.add(user)
        scope = EngagementScopeFactory()
        scope.engagements.add(ej)
        scope.groups.add(group)

    @pytest.mark.django_db
    def test_superuser(self):
        """Test that superusers can view any EJ."""
        user = UserFactory(is_superuser=True)
        ej = DataEngagementFactory()

        result = user_can_view_ej(user, ej.num_ej)
        assert result is True

    @pytest.mark.django_db
    def test_no_permission_no_scope(self):
        """Test that user without permission and without scope cannot view EJ."""
        user = UserFactory()
        ej = DataEngagementFactory()

        result = user_can_view_ej(user, ej.num_ej)
        assert result is False

    @pytest.mark.django_db
    def test_with_permission_no_scope(self):
        """Test that user with permission but without scope cannot view EJ."""
        user = UserFactory()
        ej = DataEngagementFactory()
        self._add_permission(user)

        result = user_can_view_ej(user, ej.num_ej)
        assert result is False

    @pytest.mark.django_db
    def test_no_permission_with_scope(self):
        """Test that user without permission but with scope cannot view EJ."""
        user = UserFactory()
        ej = DataEngagementFactory()
        self._add_scope(user, ej)

        result = user_can_view_ej(user, ej.num_ej)
        assert result is False

    @pytest.mark.django_db
    def test_with_permission_and_scope(self):
        """Test that user with both permission and scope can view EJ."""
        user = UserFactory()
        ej = DataEngagementFactory()
        self._add_permission(user)
        self._add_scope(user, ej)

        result = user_can_view_ej(user, ej.num_ej)
        assert result is True

    @pytest.mark.django_db
    def test_wrong_ej(self):
        """Test that user with permission and scope cannot view different EJ."""
        user = UserFactory()
        ej_allowed = DataEngagementFactory(num_ej="EJ001")
        ej_not_allowed = DataEngagementFactory(num_ej="EJ002")
        self._add_permission(user)
        self._add_scope(user, ej_allowed)

        # User should be able to view allowed EJ
        result = user_can_view_ej(user, ej_allowed.num_ej)
        assert result is True

        # User should not be able to view not allowed EJ
        result = user_can_view_ej(user, ej_not_allowed.num_ej)
        assert result is False

    @pytest.mark.django_db
    def test_multiple_scopes(self):
        """Test that user can view EJ from any of their scopes."""
        user = UserFactory()
        ej1 = DataEngagementFactory(num_ej="EJ001")
        ej2 = DataEngagementFactory(num_ej="EJ002")
        ej3 = DataEngagementFactory(num_ej="EJ003")
        self._add_permission(user)
        self._add_scope(user, ej1)
        self._add_scope(user, ej2)

        # User should be able to view all EJs from both scopes
        assert user_can_view_ej(user, ej1.num_ej) is True
        assert user_can_view_ej(user, ej2.num_ej) is True
        assert user_can_view_ej(user, ej3.num_ej) is False

    @pytest.mark.django_db
    def test_nonexistent_ej(self):
        """Test that user cannot view non-existent EJ."""
        user = UserFactory()
        ej = DataEngagementFactory(num_ej="EJ001")
        self._add_permission(user)
        self._add_scope(user, ej)

        result = user_can_view_ej(user, "NONEXISTENT")
        assert result is False
