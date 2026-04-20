"""Factory for TrackingEvent model."""

import factory

from docia.tracking.models import TrackingEvent
from tests.factories.data import random_num_ej
from tests.factories.users import UserFactory


class TrackingEventFactory(factory.django.DjangoModelFactory):
    """Factory for creating TrackingEvent instances."""

    class Meta:
        model = TrackingEvent

    category = "test_category"
    action = "test_action"
    name = "test_name"
    page_url = factory.Sequence(lambda n: f"/test-page-{n:03d}")
    num_ej = factory.LazyFunction(random_num_ej)
    user = factory.SubFactory(UserFactory)
