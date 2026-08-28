import json
from typing import Awaitable, Callable

from app.core.redis_client import redis_client


async def idempotent(key: str, ttl_seconds: int, action: Callable[[], Awaitable[dict]]) -> dict:
    """
    Ensures `action()`'s side effects happen at most once per idempotency
    key, even if the client retries the exact same request — e.g. the
    network drops right as checkout succeeds server-side, the client never
    sees the response, and retries. Without this, that retry would create
    a second set of orders and charge the card twice.

    If `action()` raises (e.g. insufficient stock), we deliberately do
    NOT cache anything — a failed attempt should be retryable with a
    fresh outcome, not permanently frozen as a failure.
    """
    cached = await redis_client.get(key)
    if cached is not None:
        return json.loads(cached)

    result = await action()
    await redis_client.set(key, json.dumps(result, default=str), ex=ttl_seconds)
    return result
