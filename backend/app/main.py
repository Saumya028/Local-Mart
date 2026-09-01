import logging

import redis.exceptions
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import (
    addresses,
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

# CORS: only the frontend's own origin is allowed to call this API with
# credentials. We deliberately do NOT use "*" here — that's a common
# shortcut in tutorials that becomes a real security gap in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
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
app.include_router(webhooks.router)


@app.get("/")
async def root():
    return {"message": "LocalMart API is running", "environment": settings.environment}
