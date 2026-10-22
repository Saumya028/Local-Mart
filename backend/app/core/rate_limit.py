import logging

import redis.exceptions
from fastapi import Depends, HTTPException, Request, status

from app.core.client_ip import client_ip
from app.core.redis_client import redis_client
from app.core.security import get_current_user
from app.models import Profile

logger = logging.getLogger(__name__)


async def _check_and_increment(key: str, limit: int, window_seconds: int) -> None:
    """
    A fixed-window counter: INCR the key, and — only on the very first
    increment of a fresh window — set it to expire after
    `window_seconds`. Simpler to reason about than a sliding-window or
    token-bucket scheme, at the cost of the classic fixed-window
    inaccuracy (a burst that straddles the boundary between two windows
    can let through up to ~2x `limit` in a short span). That trade-off is
    fine here: this exists to blunt abusive bursts and runaway
    client-side retry loops, not to enforce a precise billing-grade
    quota.

    Fails OPEN: if Redis itself is unreachable, we log a warning and let
    the request through rather than turning a Redis outage into every
    checkout in the country failing. Rate limiting is a defense-in-depth
    layer, not the thing actually guaranteeing correctness — that's the
    DB-level `stock_qty >= qty` guard and idempotency keys in
    orders.py/idempotency.py. Same fail-open philosophy as
    cache.py's cache_get_or_set and the RedisError handler in main.py.
    """
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window_seconds)
    except redis.exceptions.RedisError:
        logger.warning("rate limit check failed for %s, failing open", key, exc_info=True)
        return

    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again shortly.",
        )


def rate_limit_by_ip(action: str, limit: int, window_seconds: int):
    """
    For endpoints reached without (or before) a verified identity —
    keyed by client IP.

    The IP comes from core/client_ip.py, which only trusts
    `X-Forwarded-For` entries added by OUR proxies (TRUSTED_PROXY_COUNT).
    Set that env var on your host (1 on Railway/Render/Fly/Heroku);
    left at 0, behind a proxy, everyone shares the proxy's single IP.
    """

    async def checker(request: Request) -> None:
        await _check_and_increment(f"ratelimit:{action}:ip:{client_ip(request)}", limit, window_seconds)

    return checker


def rate_limit_by_user(action: str, limit: int, window_seconds: int):
    """
    For already-authenticated endpoints — keyed by user id rather than
    IP, so one abusive user can't get an entire shared office/NAT/campus
    network throttled, and someone rotating IPs to dodge a per-IP limit
    gains nothing since this limit follows the account, not the network
    address.

    Depends on `get_current_user` itself and returns the resolved user,
    so a route can use this AS its normal auth dependency
    (`user: Profile = Depends(rate_limit_by_user(...))`) instead of
    stacking two separate dependencies — FastAPI only resolves
    `get_current_user` once per request either way (it caches dependency
    results per request by default), so this doesn't cost a second JWT
    verification or DB lookup.
    """

    async def checker(user: Profile = Depends(get_current_user)) -> Profile:
        await _check_and_increment(f"ratelimit:{action}:user:{user.id}", limit, window_seconds)
        return user

    return checker
