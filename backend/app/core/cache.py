import json
import logging
from typing import Awaitable, Callable

import redis.exceptions

from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


async def cache_get_or_set(key: str, ttl_seconds: int, loader: Callable[[], Awaitable]):
    """
    The cache-aside pattern, in one place, so every route that needs
    caching does it the same way instead of hand-rolling get/set logic
    per endpoint.

    1. Check Redis for `key`. If present, return it — no database hit.
    2. If missing, call `loader()` (which actually queries Postgres),
       store the result in Redis with the given TTL, and return it.

    `loader` should return something JSON-serializable (a dict or list of
    dicts) — this function doesn't know or care what it represents.

    Note on caching "not found": if `loader()` returns None (e.g. a
    product that doesn't exist), we still cache that None for the TTL
    window. That's a deliberate simplification for now — it means a typo'd
    ID returns 404 quickly without hammering Postgres, at the cost of a
    freshly-created record being invisible for up to `ttl_seconds` if
    someone queried its ID moments before it existed. Not a real concern
    at this stage.

    Redis is a speed optimization here, not a source of truth — Postgres
    always has the real data. So if Redis is unreachable (an outage, or
    every retry in redis_client.py's own reconnect logic being exhausted),
    we log it and fall straight through to `loader()` instead of letting
    that turn into a 500. Shoppers get a slightly slower response instead
    of a broken page.
    """
    try:
        cached = await redis_client.get(key)
    except redis.exceptions.RedisError:
        logger.warning("cache read failed for %s, falling back to DB", key, exc_info=True)
        return await loader()

    if cached is not None:
        return json.loads(cached)

    fresh = await loader()

    try:
        await redis_client.set(key, json.dumps(fresh, default=str), ex=ttl_seconds)
    except redis.exceptions.RedisError:
        # We already have the real answer from Postgres — just failing to
        # cache it isn't worth breaking the request over. The next request
        # will simply hit Postgres again too.
        logger.warning("cache write failed for %s", key, exc_info=True)

    return fresh


async def invalidate(*keys: str) -> None:
    """
    Deletes cached entries immediately after a write — used by the Shop
    Dashboard whenever a product/shop changes, so shoppers don't see a
    stale price or "out of stock" state just because Redis hasn't
    naturally expired the old value yet. Cheap to call with no keys
    (no-op), so callers don't need to guard against that case themselves.

    Accepts one or more keys (e.g. `invalidate("shops:list", "categories:list")`)
    since a single write often needs to bust more than one cached view at once.

    If Redis is unreachable, we log and move on rather than fail the
    write that triggered this — the write itself (to Postgres) already
    succeeded by the time this runs; at worst a stale cached read sticks
    around until its TTL expires naturally.
    """
    if not keys:
        return
    try:
        await redis_client.delete(*keys)
    except redis.exceptions.RedisError:
        logger.warning("cache invalidate failed for %s", keys, exc_info=True)
