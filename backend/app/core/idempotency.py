import asyncio
import json
from typing import Awaitable, Callable

from fastapi import HTTPException

from app.core.redis_client import redis_client

# Marker stored under the key while the first request is still running.
_PENDING = "__pending__"
# If the process handling the first request dies mid-flight, the marker
# expires on its own after this long instead of blocking retries forever.
_LOCK_TTL_SECONDS = 60
# How long a duplicate request waits for the first one to finish before
# telling the client to retry.
_WAIT_SECONDS = 10
_POLL_INTERVAL = 0.2


async def idempotent(key: str, ttl_seconds: int, action: Callable[[], Awaitable[dict]]) -> dict:
    """
    Ensures `action()`'s side effects happen at most once per idempotency
    key, even if the client retries the exact same request — e.g. the
    network drops right as checkout succeeds server-side, the client never
    sees the response, and retries. Without this, that retry would create
    a second set of orders.

    Atomic: the first request claims the key with `SET NX` (a lock marker)
    BEFORE running `action()`. A duplicate that arrives while the first is
    still running does not run the action — it waits briefly for the first
    request's result and returns that, or gets a 409 if it takes too long.
    (The old GET -> run -> SET version let two simultaneous retries both
    run, creating duplicate orders.)

    If `action()` raises (e.g. insufficient stock), the lock is released
    and nothing is cached — a failed attempt stays retryable with a fresh
    outcome instead of being frozen as a failure.
    """
    claimed = await redis_client.set(key, _PENDING, nx=True, ex=_LOCK_TTL_SECONDS)

    if claimed:
        try:
            result = await action()
        except BaseException:
            await redis_client.delete(key)
            raise
        await redis_client.set(key, json.dumps(result, default=str), ex=ttl_seconds)
        return result

    # Someone else holds (or already finished) this key.
    waited = 0.0
    while True:
        cached = await redis_client.get(key)
        if cached is None:
            # Lock expired or the first attempt failed and released it —
            # this request may try for itself.
            return await idempotent(key, ttl_seconds, action)
        if cached != _PENDING:
            return json.loads(cached)
        if waited >= _WAIT_SECONDS:
            raise HTTPException(
                status_code=409,
                detail="This request is already being processed. Please check your orders before retrying.",
            )
        await asyncio.sleep(_POLL_INTERVAL)
        waited += _POLL_INTERVAL
