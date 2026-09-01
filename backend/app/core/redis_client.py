import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import settings

# A single shared Redis connection pool for the whole app.
# We import `redis_client` wherever we need cart/session/cache access —
# no need to create a new connection per request.
#
# The log showed `redis.exceptions.ConnectionError: ... An existing
# connection was forcibly closed by the remote host`. This is Upstash
# (or most hosted Redis providers) closing connections that sit idle for
# too long — the client doesn't find out until it tries to use one. It
# happens more on the free tier, and more over plain `redis://` than
# TLS `rediss://`, so double-check REDIS_URL uses `rediss://` too.
#
# The options below make that survivable instead of a 500:
#   - retry (3 attempts, exponential backoff) + retry_on_error covers the
#     exact ConnectionError/TimeoutError seen in the traceback: the first
#     write on a dead socket fails fast, and each retry re-establishes a
#     fresh connection (send_packed_command() reconnects automatically
#     whenever it sees the connection isn't alive) rather than reusing
#     the same dead one.
#   - health_check_interval pings idle connections every 10s so dead ones
#     are noticed and replaced before a real request hits them, rather
#     than waiting for a request to fail first.
#   - socket_keepalive asks the OS to keep the TCP connection alive, which
#     helps avoid it being silently dropped in the first place.
#
# This still isn't bulletproof against a sustained outage — see
# cache.py's cache_get_or_set/invalidate for how reads/writes that go
# through the cache fall back gracefully even if every retry here fails.
redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    retry=Retry(ExponentialBackoff(base=0.1, cap=1), retries=3),
    retry_on_error=[redis.ConnectionError, redis.TimeoutError, ConnectionResetError],
    health_check_interval=10,
    socket_keepalive=True,
    socket_connect_timeout=5,
)
