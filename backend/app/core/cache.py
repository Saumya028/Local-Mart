import json
from typing import Awaitable, Callable

from app.core.redis_client import redis_client


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
    """
    cached = await redis_client.get(key)
    if cached is not None:
        return json.loads(cached)

    fresh = await loader()
    await redis_client.set(key, json.dumps(fresh, default=str), ex=ttl_seconds)
    return fresh
