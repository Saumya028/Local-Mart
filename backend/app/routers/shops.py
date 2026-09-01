import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set, invalidate
from app.core.db import get_db
from app.core.security import require_role
from app.core.utils import parse_uuid_or_404
from app.models import Profile, Shop
from app.schemas.shop import ShopCreate, ShopOut

router = APIRouter(prefix="/shops", tags=["shops"])


@router.get("", response_model=list[ShopOut])
async def list_shops(
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Backs the "Shops near you" section on the Landing page.

    We only cache the unfiltered call — that's the one every Landing page
    load hits identically. A `?category=` filtered call is rarer and more
    varied, so it goes straight to Postgres; caching every possible filter
    value isn't worth the complexity at this stage.
    """
    if category is None:
        async def load():
            result = await db.execute(
                select(Shop)
                .where(Shop.is_active.is_(True))
                .order_by(Shop.rating.desc())
                .limit(50)
            )
            shops = result.scalars().all()
            return [ShopOut.model_validate(s).model_dump(mode="json") for s in shops]

        return await cache_get_or_set("shops:list", ttl_seconds=60, loader=load)

    result = await db.execute(
        select(Shop)
        .where(Shop.is_active.is_(True), Shop.category == category)
        .order_by(Shop.rating.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("", response_model=ShopOut)
async def create_shop(
    payload: ShopCreate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Creating a shop is restricted to accounts that are ALREADY
    shop_owner or admin — not self-service for a plain customer. Becoming
    a shop_owner in the first place is an explicit promotion, not
    something an account grants itself by clicking a button (see
    scripts/promote_user.py until the Admin Panel in Phase 6 ships a
    proper UI for this).

    This lets an existing shop owner run more than one shop, while a
    customer hitting this endpoint gets a clean 403 from require_role
    before ever reaching this function body.
    """
    shop = Shop(id=uuid.uuid4(), owner_id=user.id, name=payload.name, category=payload.category)
    db.add(shop)
    await db.commit()
    await db.refresh(shop)

    # A brand new shop should show up in "Shops near you" and the
    # category counts immediately, not up to 60s/5min later.
    await invalidate("shops:list", "categories:list")
    return shop


@router.get("/{shop_id}", response_model=ShopOut)
async def get_shop(shop_id: str, db: AsyncSession = Depends(get_db)):
    sid = parse_uuid_or_404(shop_id, "Shop")

    async def load():
        result = await db.execute(select(Shop).where(Shop.id == sid))
        shop = result.scalar_one_or_none()
        return ShopOut.model_validate(shop).model_dump(mode="json") if shop else None

    data = await cache_get_or_set(f"shop:{shop_id}", ttl_seconds=60, loader=load)
    if data is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    return data
