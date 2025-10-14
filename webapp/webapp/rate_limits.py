import datetime

from sqlalchemy import text

from .db import get_conn


def check_rate_limit(key, limit):
    """
    Rate limit executions per day for a specific key.

    Args:
        key (str): The identifier for rate limiting
        limit (int): Maximum number of executions allowed per day

    Returns:
        bool: True if request should proceed, False if rate limited
    """
    now = datetime.datetime.now()
    today = now.date()

    key = today.isoformat() + "__" + key

    with get_conn().connect() as conn:

            # Try to get the current rate limit record
            record = conn.execute(
                text("SELECT key, counter FROM rate_limits WHERE key = :key"),
                dict(key=key),
            ).fetchone()

            if record is None:
                # No record exists, create a new one with counter=1
                conn.execute(
                    text("INSERT INTO rate_limits (key, counter, expiry) VALUES (:key, 0, :expiry)"),
                    dict(key=key, expiry=today + datetime.timedelta(days=1)),
                )
                conn.commit()
                counter = 0
            else:
                key, counter = record

            # If we're under the limit, increment the counter
            if counter < limit:
                conn.execute(
                    text("UPDATE rate_limits SET counter = counter + 1 WHERE key = :key"),
                    dict(key=key),
                )
                conn.commit()
                return True
            # Rate limit exceeded
            else:
                return False