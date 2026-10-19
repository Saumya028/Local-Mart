"""Admin > Recommendations: is the model healthy, and is it actually helping?"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.order_status import RECOGNIZED_STATUSES
from app.core.security import require_role
from app.models import Profile, RecommendationRun
from app.schemas.recommendation import (
    RecoHealthOut,
    RecoMetricRow,
    RecoMetricsOut,
    RecoRunOut,
    RecoStatusOut,
)

router = APIRouter(prefix="/admin/recommendations", tags=["admin-recommendations"])
RequireAdmin = require_role("admin")

ATTRIBUTION_WINDOW_DAYS = 7


def _run_out(run: RecommendationRun) -> RecoRunOut:
    return RecoRunOut(
        id=run.id,
        status=run.status,
        is_active=run.is_active,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=(run.stats or {}).get("duration_seconds"),
        error=run.error,
        stats=run.stats or {},
    )


async def model_health(db: AsyncSession) -> tuple[str, RecommendationRun | None, float | None]:
    """(ok | stale | no_model | disabled, active run, hours since it was built)."""
    if not settings.reco_enabled:
        return "disabled", None, None
    active = (
        await db.execute(select(RecommendationRun).where(RecommendationRun.is_active.is_(True)))
    ).scalar_one_or_none()
    if active is None:
        return "no_model", None, None
    built = active.finished_at or active.started_at
    age = (datetime.now(timezone.utc) - built).total_seconds() / 3600
    return ("stale" if age > settings.reco_stale_hours else "ok"), active, round(age, 1)


async def health_summary(db: AsyncSession) -> RecoHealthOut:
    health, active, age = await model_health(db)
    return RecoHealthOut(status=health, age_hours=age, run_id=active.id if active else None)


@router.get("/status", response_model=RecoStatusOut)
async def status(admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)):
    health, active, age = await model_health(db)
    recent = (
        await db.execute(select(RecommendationRun).order_by(RecommendationRun.started_at.desc()).limit(10))
    ).scalars().all()
    return RecoStatusOut(
        enabled=settings.reco_enabled,
        holdout_pct=settings.reco_holdout_pct,
        min_co_buyers=settings.reco_min_co_buyers,
        excluded_categories=settings.reco_excluded_category_list,
        health=health,
        active_run=_run_out(active) if active else None,
        age_hours=age,
        stale_after_hours=settings.reco_stale_hours,
        recent_runs=[_run_out(r) for r in recent],
    )


# Impressions/clicks/add-to-carts per (surface, arm), plus orders and revenue
# that followed a click or add-to-cart on that exact product by the same
# customer within the attribution window. DISTINCT on the order line so a
# click AND an add-to-cart on one product don't count its revenue twice.
_METRICS_SQL = text(
    """
    WITH counts AS (
        SELECT surface, variant,
               count(*) FILTER (WHERE event = 'impression')  AS impressions,
               count(*) FILTER (WHERE event = 'click')       AS clicks,
               count(*) FILTER (WHERE event = 'add_to_cart') AS add_to_carts
        FROM recommendation_events
        WHERE created_at >= :since
        GROUP BY surface, variant
    ),
    attributed AS (
        SELECT surface, variant,
               count(DISTINCT order_id) AS orders,
               COALESCE(sum(line_total), 0) AS revenue
        FROM (
            SELECT DISTINCT e.surface, e.variant, o.id AS order_id, oi.id AS item_id,
                   oi.unit_price * oi.quantity AS line_total
            FROM recommendation_events e
            JOIN orders o
              ON o.user_id = e.user_id
             AND o.created_at >= e.created_at
             AND o.created_at <  e.created_at + make_interval(days => :window)
             AND o.status = ANY(:statuses)
            JOIN order_items oi ON oi.order_id = o.id AND oi.product_id = e.product_id
            WHERE e.event IN ('click', 'add_to_cart')
              AND e.user_id IS NOT NULL
              AND e.created_at >= :since
        ) t
        GROUP BY surface, variant
    )
    SELECT c.surface, c.variant, c.impressions, c.clicks, c.add_to_carts,
           COALESCE(a.orders, 0) AS orders, COALESCE(a.revenue, 0) AS revenue
    FROM counts c
    LEFT JOIN attributed a ON a.surface = c.surface AND a.variant = c.variant
    ORDER BY c.surface, c.variant
    """
)


@router.get("/metrics", response_model=RecoMetricsOut)
async def metrics(
    days: int = Query(default=30, ge=1, le=90),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        _METRICS_SQL, {"since": since, "window": ATTRIBUTION_WINDOW_DAYS, "statuses": list(RECOGNIZED_STATUSES)}
    )
    rows = []
    for surface, variant, imps, clicks, atcs, orders, revenue in result.all():
        rows.append(
            RecoMetricRow(
                surface=surface,
                variant=variant,
                impressions=imps,
                clicks=clicks,
                add_to_carts=atcs,
                ctr=round(clicks / imps, 4) if imps else 0.0,
                add_to_cart_rate=round(atcs / imps, 4) if imps else 0.0,
                orders=orders,
                revenue=Decimal(revenue),
                revenue_per_1000_impressions=round(float(revenue) / imps * 1000, 2) if imps else 0.0,
            )
        )
    return RecoMetricsOut(days=days, rows=rows)
