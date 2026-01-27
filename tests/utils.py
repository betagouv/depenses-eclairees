"""Test utilities and helper functions."""

from django.test import TestCase


def assert_queryset_equal(*args, **kwargs):
    """Helper function to assert queryset equality using Django's TestCase method."""
    return TestCase().assertQuerySetEqual(*args, **kwargs)
