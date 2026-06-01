import datetime
import inspect

from django.db.models import Manager
from django.test import TestCase
from django.utils import timezone


def tz_datetime(value: str | datetime.date | datetime.datetime = None):
    """Create a timezone-aware datetime using Django's default timezone.

    Args:
        value: A datetime.datetime, datetime.date, iso format string, or None.
              If None, returns the current time in the default timezone.

    Returns:
        A timezone-aware datetime object.
    """
    if value is None:
        # timezone.now() returns UTC, convert to default timezone
        return timezone.localtime(timezone.now())
    elif isinstance(value, datetime.datetime):
        return timezone.make_aware(value)
    elif isinstance(value, datetime.date):
        return timezone.make_aware(datetime.datetime(value.year, value.month, value.day))
    elif isinstance(value, str):
        dt = datetime.datetime.fromisoformat(value)
        return timezone.make_aware(dt)
    else:
        return timezone.make_aware(datetime.datetime(*value))


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


def bind_arguments(original_function, *args, **kwargs) -> dict:
    """Ensure the given args and kwargs match the function's signature."""
    sig = inspect.signature(original_function)
    bound_args = sig.bind(*args, **kwargs)
    return bound_args.arguments
