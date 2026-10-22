import logging

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.db import engine
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

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
    except Exception:
        # Never echo the exception to the caller: DB/Redis errors can
        # contain hostnames, usernames or connection-string fragments.
        # /health is public; the detail goes to the (private) logs instead.
        logger.exception("health check: database unreachable")
        status["database"] = "error"

    # Check Redis: PING is the standard connectivity check.
    try:
        pong = await redis_client.ping()
        status["redis"] = "ok" if pong else "error"
    except Exception:
        logger.exception("health check: redis unreachable")
        status["redis"] = "error"

    return status


@router.get("/health/recommendations")
async def recommendations_health(response: Response):
    """
    For an uptime monitor: 200 while the recommendation model is fresh (or
    simply not built yet / switched off), 503 once the active model is older
    than RECO_STALE_HOURS — i.e. the nightly build has been failing or
    getting rejected for a while. Shelves keep working on the old model
    meanwhile; this is the nudge to go look.
    """
    # imported here so a problem in the admin module can't break /health
    from app.core.db import AsyncSessionLocal
    from app.routers.admin_recommendations import health_summary

    async with AsyncSessionLocal() as db:
        summary = await health_summary(db)
    if summary.status == "stale":
        response.status_code = 503
    return summary
