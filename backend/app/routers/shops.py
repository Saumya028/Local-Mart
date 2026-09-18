import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set, invalidate
from app.core.db import get_db
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Profile, Shop
from app.schemas.shop import ShopCreate, ShopOut

router = APIRouter(prefix="/shops", tags=["shops"])


@router.get("", response_model=list[ShopOut])
async def list_shops(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Case-insensitive substring match on shop name"),
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Backs the "Shops near you" section on the Landing page, and — with
    `q`/`category` — the /stores browse-all page's search and category
    filter.

    We only cache the fully-unfiltered call at the default limit — that's
    the one every Landing page load hits identically. A `q`/`category`
    filtered call, or a non-default `limit`, is rarer and more varied, so
    it goes straight to Postgres; caching every possible combination
    isn't worth the complexity at this stage.
    """
    # A shop must be BOTH is_active (currently open) AND approval_status
    # == "approved" (an admin has signed off on it) to show up in the
    # public catalog — a brand-new, still-pending application is invisible
    # here even though its is_active default is fine, exactly like a
    # rejected/deactivated shop is.
    if category is None and q is None and limit == 50:
        async def load():
            result = await db.execute(
                select(Shop)
                .where(Shop.is_active.is_(True), Shop.approval_status == "approved")
                .order_by(Shop.rating.desc())
                .limit(50)
            )
            shops = result.scalars().all()
            return [ShopOut.model_validate(s).model_dump(mode="json") for s in shops]

        return await cache_get_or_set("shops:list", ttl_seconds=60, loader=load)

    stmt = select(Shop).where(Shop.is_active.is_(True), Shop.approval_status == "approved")
    if category is not None:
        stmt = stmt.where(Shop.category == category)
    if q:
        stmt = stmt.where(Shop.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Shop.rating.desc()).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ShopOut)
async def create_shop(
    payload: ShopCreate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Applying to sell is self-service for any authenticated, non-suspended
    account — a plain customer submitting this becomes a shop_owner
    immediately (see the promotion below), no separate admin step
    required to unlock the Shop Dashboard. What an admin still reviews
    afterward is the SHOP LISTING itself (approval_status, below) —
    becoming a seller and getting your storefront live are two different
    gates. An existing shop_owner hitting this again just adds another
    shop under the same account; an admin can do the same.
    """
    # New shops start "pending"/unverified and closed — they only become
    # visible on the storefront once an admin approves them from the
    # Manage Shops queue (see routers/admin.py's approve_shop). docs_status
    # is "submitted" (not the model's Python-side "pending" default)
    # because ShopCreate.documents already required at least one file —
    # there's something on file for an admin to review from the start.
    shop = Shop(
        id=uuid.uuid4(),
        owner_id=user.id,
        name=payload.name,
        category=payload.category,
        is_active=False,
        approval_status="pending",
        docs_status="submitted",
        documents=[d.model_dump() for d in payload.documents],
    )
    db.add(shop)

    # The actual self-service promotion: a plain customer applying to
    # sell becomes a shop_owner right here, in the same transaction as
    # their shop application — not a separate step anyone has to
    # perform on their behalf. `user` is already attached to this same
    # `db` session (it was loaded by get_current_user above), so mutating
    # it and committing persists both the new shop and the role change
    # atomically. An admin applying again just stays admin.
    if user.role == "customer":
        user.role = "shop_owner"

    await db.commit()
    await db.refresh(shop)

    # A brand new shop should show up in "Shops near you" and the
    # category counts immediately, not up to 60s/5min later.
    await invalidate("shops:list", "categories:list")
    return shop


@router.get("/{shop_id}", response_model=ShopOut)
async def get_shop(shop_id: str, db: AsyncSession = Depends(get_db)):
    """
    Backs the public storefront page (`/store/[id]`). Filters on the same
    is_active + approval_status == "approved" rule as list_shops above —
    without this, a pending/rejected/deactivated shop would still be
    directly fetchable by anyone who had (or guessed) its ID, even though
    it's invisible everywhere it'd normally be discovered from.
    """
    sid = parse_uuid_or_404(shop_id, "Shop")

    async def load():
        result = await db.execute(
            select(Shop).where(
                Shop.id == sid, Shop.is_active.is_(True), Shop.approval_status == "approved"
            )
        )
        shop = result.scalar_one_or_none()
        return ShopOut.model_validate(shop).model_dump(mode="json") if shop else None

    data = await cache_get_or_set(f"shop:{shop_id}", ttl_seconds=60, loader=load)
    if data is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    return data
