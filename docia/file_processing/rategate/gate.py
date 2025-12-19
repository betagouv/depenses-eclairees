import time
from datetime import timedelta

from django.db import connection, transaction

from .models import RateGateState


def pg_clock_timestamp():
    # Returns an aware datetime (timestamptz) from Postgres
    with connection.cursor() as cur:
        cur.execute("SELECT clock_timestamp()")
        (ts,) = cur.fetchone()
        return ts


class RateGate:
    """
    Global min-spacing between request *starts* across nodes.

    - Correctness via SELECT ... FOR UPDATE row lock
    - Uses Postgres clock_timestamp() to avoid client clock drift
    - Stores next_allowed_at as timestamptz (DateTimeField)
    """

    def __init__(self, rate_per_minute: int, key: str):
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be > 0")
        self.key = key
        self.interval = timedelta(seconds=60.0 / float(rate_per_minute))

    def wait_turn(self) -> None:
        delay = self._reserve_delay_seconds()
        if delay > 0:
            time.sleep(delay)

    def _reserve_delay_seconds(self) -> float:
        with transaction.atomic(durable=True):
            # Ensure row exists (no lock yet)
            RateGateState.objects.get_or_create(key=self.key)

            # Lock the state row so only one node updates at a time
            state = RateGateState.objects.select_for_update().get(key=self.key)

            # IMPORTANT: get server time AFTER acquiring the lock
            now = pg_clock_timestamp()

            start = now
            if state.next_allowed_at and state.next_allowed_at > now:
                start = state.next_allowed_at

            state.next_allowed_at = start + self.interval
            state.save(update_fields=["next_allowed_at"])

            return (start - now).total_seconds()
