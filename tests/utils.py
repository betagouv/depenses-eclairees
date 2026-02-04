from django.db.models import Manager
from django.test import TestCase


def assert_queryset_equal(qs, values, transform=None, ordered=False, msg=None):
    """Helper function to assert queryset equality using Django's TestCase method."""
    if isinstance(qs, Manager):
        qs = qs.all()
    return TestCase().assertQuerySetEqual(
        qs=qs,
        values=values,
        transform=transform,
        ordered=ordered,
        msg=msg,
    )
