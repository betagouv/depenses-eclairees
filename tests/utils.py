import inspect

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


def bind_arguments(original_function, *args, **kwargs) -> dict:
    """Ensure the given args and kwargs match the function's signature."""
    sig = inspect.signature(original_function)
    bound_args = sig.bind(*args, **kwargs)
    return bound_args.arguments
