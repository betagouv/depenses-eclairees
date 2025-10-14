import datetime

from django.contrib.postgres.functions import RandomUUID
from django.db import connection, models

MAX_COUNT = 1000000


class RateLimitCountManager(models.Manager):
    def increment(self, key: str, interval: int):
        SQL = """
            INSERT INTO docia_ratelimitcount (key, interval, count, expiry)
            VALUES (%(key)s, %(interval)s, 1, %(expiry)s)
            ON CONFLICT (key, interval) DO UPDATE
                SET count  = CASE
                                 WHEN docia_ratelimitcount.count >= %(max_count)s
                                     THEN docia_ratelimitcount.count
                                 WHEN %(now)s < docia_ratelimitcount.expiry
                                     THEN docia_ratelimitcount.count + 1
                                 ELSE 1
                    END,
                    expiry = CASE
                                 WHEN %(now)s < docia_ratelimitcount.expiry
                                     THEN docia_ratelimitcount.expiry
                                 ELSE %(expiry)s
                        END
            RETURNING docia_ratelimitcount.*;
        """
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        with connection.cursor() as cursor:
            cursor.execute(
                SQL,
                {
                    "key": key,
                    "interval": interval,
                    "expiry": now + datetime.timedelta(seconds=interval),
                    "now": now,
                    "max_count": MAX_COUNT,
                },
            )
            data = cursor.fetchone()
            columns = [col[0] for col in cursor.description]
            data_dict = dict(zip(columns, data))
            return RateLimitCount(**data_dict)


class RateLimitCount(models.Model):
    id = models.UUIDField(
        primary_key=True,
        db_default=RandomUUID(),
        editable=False,
    )
    key = models.CharField()
    interval = models.IntegerField()
    count = models.BigIntegerField(default=0)
    expiry = models.DateTimeField()

    objects = RateLimitCountManager()

    class Meta:
        unique_together = [("key", "interval")]

    def __str__(self):
        return f"{self.key} int={self.interval} = {self.count}"
