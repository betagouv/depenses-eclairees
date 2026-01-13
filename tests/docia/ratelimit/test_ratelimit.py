from django.contrib.auth import get_user_model

import pytest
from freezegun import freeze_time

from docia.ratelimit.models import RateLimitCount
from docia.ratelimit.services import check_rate_limit, check_rate_limit_for_user
from tests.factories.users import UserFactory

now = "2025-10-08T10:00:00+00:00"
now_plus_1h = "2025-10-08T11:00:00+00:00"
User = get_user_model()


@pytest.mark.django_db
def test_first_call():
    with freeze_time(now):
        r = check_rate_limit("toto", 1000, 3600)
    assert r.key == "toto"
    assert r.interval == 3600
    assert r.count == 1
    assert r.expiry.isoformat() == now_plus_1h
    assert not r.limited


@pytest.mark.django_db
def test_successive_call():
    RateLimitCount.objects.create(
        key="toto",
        interval=3600,
        count=56,
        expiry=now_plus_1h,
    )
    with freeze_time(now):
        r = check_rate_limit("toto", 1000, 3600)
    assert r.key == "toto"
    assert r.interval == 3600
    assert r.count == 57
    assert r.expiry.isoformat() == now_plus_1h
    assert not r.limited


@pytest.mark.django_db
def test_rate_limit():
    RateLimitCount.objects.create(
        key="toto",
        interval=3600,
        count=1000,
        expiry=now_plus_1h,
    )
    with freeze_time(now):
        r = check_rate_limit("toto", 1000, 3600)
    assert r.key == "toto"
    assert r.interval == 3600
    assert r.count == 1001
    assert r.expiry.isoformat() == now_plus_1h
    assert r.limited


@pytest.mark.django_db
def test_expiry():
    RateLimitCount.objects.create(
        key="toto",
        interval=3600,
        count=1000,
        expiry=now,
    )
    with freeze_time(now):
        r = check_rate_limit("toto", 1000, 3600)
    assert r.key == "toto"
    assert r.interval == 3600
    assert r.count == 1
    assert r.expiry.isoformat() == now_plus_1h
    assert not r.limited


@pytest.mark.django_db
def test_for_user():
    user = UserFactory()
    with freeze_time(now):
        r = check_rate_limit_for_user(user, 1000, 3600)
    assert r.key == str(user.id)
    assert r.interval == 3600
    assert r.count == 1
    assert r.expiry.isoformat() == now_plus_1h
    assert not r.limited
