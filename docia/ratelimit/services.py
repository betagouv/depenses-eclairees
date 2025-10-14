from docia.ratelimit.models import MAX_COUNT, RateLimitCount


def check_rate_limit(key: str, limit: int, interval: int):
    assert len(key) < 500
    counter = RateLimitCount.objects.increment(key, interval)
    if counter.count > limit or counter.count >= MAX_COUNT:
        counter.limited = True
    else:
        counter.limited = False
    return counter


def check_rate_limit_for_user(user, limit: int, interval: int):
    return check_rate_limit(
        key=str(user.id),
        limit=limit,
        interval=interval,
    )
