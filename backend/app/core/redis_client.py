import redis.asyncio as redis

from app.core.config import settings

# A single shared Redis connection pool for the whole app.
# We import `redis_client` wherever we need cart/session/cache access —
# no need to create a new connection per request.
redis_client = redis.from_url(settings.redis_url, decode_responses=True)
