from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import engine
from app.core.redis_client import redis_client

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Proves the whole chain is wired correctly: API -> Postgres, API -> Redis.

    This is the very first endpoint we build on purpose. Everything else
    we add later depends on these two connections actually working, so we
    want a fast, obvious way to check that at any point — locally, in CI,
    or in production.
    """
    status = {"api": "ok", "database": "unknown", "redis": "unknown"}

    # Check Postgres: run the simplest possible query.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {e}"

    # Check Redis: PING is the standard connectivity check.
    try:
        pong = await redis_client.ping()
        status["redis"] = "ok" if pong else "error: no pong"
    except Exception as e:
        status["redis"] = f"error: {e}"

    return status
