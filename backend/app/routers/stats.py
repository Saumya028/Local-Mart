from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set
from app.core.db import get_db
from app.models import Profile, Shop
from app.schemas.stats import PlatformStatsOut

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=PlatformStatsOut)
async def platform_stats(db: AsyncSession = Depends(get_db)):
    """
    Genuinely public (no auth) — unlike /admin/dashboard-summary, this is
    two counts intended for anonymous visitors on the Landing page, not
    an admin. Cached for the same reason /categories is: it scans full
    tables and doesn't need to be second-fresh for marketing copy.
    """

    async def load():
        total_shops = await db.scalar(
            select(func.count()).select_from(Shop).where(
                Shop.is_active.is_(True), Shop.approval_status == "approved"
            )
        )
        total_customers = await db.scalar(
            select(func.count()).select_from(Profile).where(Profile.role == "customer")
        )
        return {"total_shops": total_shops, "total_customers": total_customers}

    return await cache_get_or_set("platform:stats", ttl_seconds=300, loader=load)
