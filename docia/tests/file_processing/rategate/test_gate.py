from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from docia.file_processing.llm.rategate.gate import RateGate
from docia.file_processing.llm.rategate.models import RateGateState


@pytest.fixture
def cleanup_rate_gate_state():
    """Fixture to clean up the RateGateState objects after tests"""
    yield
    # Clean up after the test
    RateGateState.objects.all().delete()


@pytest.fixture
def frozen_datetime():
    """Return a fixed datetime for testing"""
    return datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_pg_clock(frozen_datetime):
    """Mock the pg_clock_timestamp function to return a fixed time"""
    with patch("docia.file_processing.llm.rategate.gate.pg_clock_timestamp") as mock:
        mock.return_value = frozen_datetime
        yield mock


def test_init_with_valid_rate():
    # Test initializing with valid rate_per_minute
    gate = RateGate(rate_per_minute=10, key="toto")
    assert gate.key == "toto"
    assert gate.interval == timedelta(seconds=6.0)  # 60/10 = 6 seconds


def test_init_with_invalid_rate():
    # Test initializing with invalid rate_per_minute
    with pytest.raises(ValueError) as excinfo:
        RateGate(rate_per_minute=0, key="test")
    assert "rate_per_minute must be > 0" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        RateGate(rate_per_minute=-5, key="test")
    assert "rate_per_minute must be > 0" in str(excinfo.value)


@pytest.mark.django_db
def test_reserve_delay_no_previous(mock_pg_clock, frozen_datetime):
    test_key = "test_no_previous"

    # Create a gate with a 10 per minute rate (6-second interval)
    gate = RateGate(rate_per_minute=10, key=test_key)

    # Test the method
    delay = gate._reserve_delay_seconds()

    # Verify behavior
    assert delay == 0  # No delay when no previous reservation

    # Verify the database state was updated
    state = RateGateState.objects.get(key=test_key)
    expected_next_allowed = frozen_datetime + timedelta(seconds=6.0)
    assert state.next_allowed_at == expected_next_allowed


@pytest.mark.django_db
def test_reserve_delay_with_future_reservation(mock_pg_clock, frozen_datetime):
    test_key = "test_future_reservation"

    # Create initial state with a future next_allowed_at
    future_time = frozen_datetime + timedelta(seconds=3)

    # Create the initial state in the database
    state = RateGateState.objects.create(key=test_key, next_allowed_at=future_time)

    # Create a gate with a 10 per minute rate (6-second interval)
    gate = RateGate(rate_per_minute=10, key=test_key)

    # Test the method
    delay = gate._reserve_delay_seconds()

    # Verify behavior
    assert delay == 3.0  # Should delay 3 seconds

    # Verify the database state was updated correctly
    state.refresh_from_db()
    expected_next_allowed = future_time + timedelta(seconds=6.0)
    assert state.next_allowed_at == expected_next_allowed


@pytest.mark.django_db
def test_reserve_delay_with_past_reservation(mock_pg_clock, frozen_datetime):
    test_key = "test_past_reservation"

    # Create initial state with a past next_allowed_at
    past_time = frozen_datetime - timedelta(seconds=5)

    # Create the initial state in the database
    state = RateGateState.objects.create(key=test_key, next_allowed_at=past_time)

    # Create a gate with a 10 per minute rate (6-second interval)
    gate = RateGate(rate_per_minute=10, key=test_key)

    # Test the method
    delay = gate._reserve_delay_seconds()

    # Verify behavior
    assert delay == 0.0  # No delay when the reservation is in the past

    # Verify the database state was updated correctly
    state.refresh_from_db()
    expected_next_allowed = frozen_datetime + timedelta(seconds=6.0)
    assert state.next_allowed_at == expected_next_allowed


@pytest.mark.django_db
def test_wait_turn_no_delay(mock_pg_clock):
    with patch("time.sleep") as mock_sleep:
        # Create a gate with a test key
        gate = RateGate(rate_per_minute=10, key="test_wait_turn_no_delay")

        # Call wait_turn which should not need to sleep
        gate.wait_turn()

        # Verify sleep wasn't called
        mock_sleep.assert_not_called()


@pytest.mark.django_db
def test_wait_turn_with_delay(mock_pg_clock, frozen_datetime):
    # Create a state with a future next_allowed_at
    test_key = "test_wait_turn_with_delay"
    future_time = frozen_datetime + timedelta(seconds=2.5)

    # Create the initial state in the database
    RateGateState.objects.create(key=test_key, next_allowed_at=future_time)

    with patch("time.sleep") as mock_sleep:
        # Create a gate with the same test key
        gate = RateGate(rate_per_minute=10, key=test_key)

        # Call wait_turn which should sleep
        gate.wait_turn()

        # Verify sleep was called with the expected delay
        mock_sleep.assert_called_once_with(2.5)


@pytest.mark.django_db
def test_different_keys_isolation(mock_pg_clock, frozen_datetime):
    # Create two gates with different keys
    key_a = "test_key_a"
    key_b = "test_key_b"

    gate_a = RateGate(rate_per_minute=10, key=key_a)  # 6-second interval
    gate_b = RateGate(rate_per_minute=20, key=key_b)  # 3-second interval

    # Test with both gates
    delay_a = gate_a._reserve_delay_seconds()
    delay_b = gate_b._reserve_delay_seconds()

    # Verify behavior
    assert delay_a == 0.0
    assert delay_b == 0.0

    # Verify database states were updated with correct intervals
    state_a = RateGateState.objects.get(key=key_a)
    state_b = RateGateState.objects.get(key=key_b)

    assert state_a.next_allowed_at == frozen_datetime + timedelta(seconds=6.0)  # 60/10
    assert state_b.next_allowed_at == frozen_datetime + timedelta(seconds=3.0)  # 60/20


@pytest.mark.django_db
def test_consecutive_calls(mock_pg_clock, frozen_datetime):
    test_key = "test_consecutive_calls"
    gate = RateGate(rate_per_minute=10, key=test_key)  # 6-second interval

    # First call should have no delay
    delay1 = gate._reserve_delay_seconds()
    assert delay1 == 0.0

    # Second call should have a 6-second delay
    delay2 = gate._reserve_delay_seconds()
    assert delay2 == 6.0

    # Verify the next_allowed_at in database
    state = RateGateState.objects.get(key=test_key)
    expected_time = frozen_datetime + timedelta(seconds=12.0)  # 2 intervals
    assert state.next_allowed_at == expected_time

    # Third call should have a 12-second delay
    delay2 = gate._reserve_delay_seconds()
    assert delay2 == 12.0

    # Verify the next_allowed_at in database
    state = RateGateState.objects.get(key=test_key)
    expected_time = frozen_datetime + timedelta(seconds=18.0)  # 3 intervals
    assert state.next_allowed_at == expected_time


@pytest.mark.django_db
def test_with_freezegun():
    test_key = "test_freezegun"

    # Use freezegun to set the time
    frozen_now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    with patch("docia.file_processing.llm.rategate.gate.pg_clock_timestamp", autospec=True) as mock_pg_clock:
        with freeze_time(frozen_now):
            # Mock pg_clock_timestamp to return the freezegun time
            mock_pg_clock.return_value = frozen_now
            # Create a gate
            gate = RateGate(rate_per_minute=10, key=test_key)  # 6-second interval

            # First call
            delay1 = gate._reserve_delay_seconds()
            assert delay1 == 0.0

            # Verify state
            state = RateGateState.objects.get(key=test_key)
            assert state.next_allowed_at == frozen_now + timedelta(seconds=6.0)

        # Move time forward 2 seconds
        frozen_now = frozen_now + timedelta(seconds=2)
        with freeze_time(frozen_now):
            # Mock pg_clock_timestamp to return new time
            mock_pg_clock.return_value = frozen_now
            # Second call should have 4 seconds of delay (6 - 2 = 4)
            delay2 = gate._reserve_delay_seconds()
            assert delay2 == 4.0

            # Verify updated state
            state.refresh_from_db()
            assert state.next_allowed_at == frozen_now + timedelta(seconds=10.0)
