import logging
import uuid

import redis.exceptions
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.observability import init_sentry
from app.core.request_context import set_request_id

# Logging must be configured, and Sentry initialized, before anything
# else below has a chance to log or raise — including router imports,
# which construct module-level objects (e.g. the Razorpay client in
# orders.py/webhooks.py) that could themselves warn or fail.
setup_logging(settings.log_level)
init_sentry()

from app.routers import (  # noqa: E402
    addresses,
    admin,
    auth,
    cart,
    categories,
    health,
    orders,
    products,
    shop_dashboard,
    shops,
    webhooks,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LocalMart API",
    version="0.1.0",
    description="Backend for the LocalMart multi-vendor marketplace platform.",
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Gives every request a `request_id` — either the one the caller
    already supplied via an `X-Request-ID` header (the frontend's
    apiClient.ts generates one per call), or a fresh UUID if it didn't.
    Stored in a contextvar (core/request_context.py) so every log line
    emitted anywhere while handling this request — in a router, in
    core/cache.py, wherever — picks it up automatically without it being
    threaded through every function call by hand.

    Echoed back as a response header too, so the frontend (or a curl'ing
    developer) can see exactly which ID to search server logs for if a
    request fails: "trace one request across frontend -> backend" from
    the roadmap's own wording.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)

# CORS: only known frontend origin(s) are allowed to call this API with
# credentials. We deliberately do NOT use "*" here — that's a common
# shortcut in tutorials that becomes a real security gap in production.
# `cors_origins` (core/config.py) splits FRONTEND_ORIGIN on commas so
# staging and prod can both be listed without code changes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(redis.exceptions.RedisError)
async def redis_error_handler(request: Request, exc: redis.exceptions.RedisError):
    """
    Endpoints that read cached data (categories, shops list, product
    detail) already degrade gracefully on their own — see
    core/cache.py's cache_get_or_set/invalidate, which fall back to
    Postgres instead of raising.

    But some endpoints genuinely NEED Redis — the cart (core/cart.py)
    and checkout idempotency (core/idempotency.py) both use it as the
    actual source of truth, not just a cache, so there's no sensible
    fallback if it's unreachable. Without this handler, a RedisError
    from those would bubble up as a raw 500 with a Python traceback
    leaking into the response. This turns that into a clean, expected
    503 instead — same underlying issue, but the frontend can show
    "please try again" instead of a broken page, and the traceback
    still goes to the server logs below for debugging.
    """
    logger.warning("Unhandled Redis error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "A temporary storage issue occurred. Please try again."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    The safety net underneath everything else. FastAPI's own default
    handlers still deal with `HTTPException` (a deliberate 404/403/etc.
    from a route) and request validation errors before this ever runs —
    this only catches genuinely UNEXPECTED exceptions: a bug, a null
    somewhere it shouldn't be, a third-party client raising something we
    didn't anticipate.

    Without this, an unhandled exception would either leak a raw Python
    traceback to the client (if DEBUG-style behavior is on somewhere in
    the stack) or just show up as an opaque, unlogged connection reset —
    neither of which is "a failed [...] fetch shouldn't break the whole
    page" from the roadmap. This turns it into one clean JSON 500 with a
    request_id the person can report, while the real traceback still
    goes to structured logs (and Sentry, if configured) for us to debug.
    """
    logger.exception(
        "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again."},
    )


# Routers get registered here. Each new domain (auth, shops, products,
# cart, orders...) gets its own router file and one line added below —
# main.py itself should stay small forever.
app.include_router(health.router, tags=["health"])
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(shops.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(addresses.router)
app.include_router(orders.router)
app.include_router(shop_dashboard.router)
app.include_router(admin.router)
app.include_router(webhooks.router)


@app.get("/")
async def root():
    return {"message": "LocalMart API is running", "environment": settings.environment}
