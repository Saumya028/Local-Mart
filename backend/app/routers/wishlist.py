import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Product, Profile, Shop, WishlistItem
from app.schemas.product import ProductOut
from app.schemas.wishlist import WishlistAddRequest, WishlistItemOut

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[WishlistItemOut])
async def list_wishlist(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    My Account > Wishlist. Only ever returns items for the CURRENT
    product (an inner join to products, not outer) — if a product is
    ever hard-deleted, WishlistItem.product_id's ON DELETE CASCADE (see
    the model) already removes the row, so there's nothing dangling to
    filter out here; the join is just how we fetch the product's current
    details.
    """
    stmt = (
        select(WishlistItem, Product, Shop.name)
        .join(Product, Product.id == WishlistItem.product_id)
        .join(Shop, Shop.id == Product.shop_id)
        .where(WishlistItem.user_id == user.id)
        .order_by(WishlistItem.created_at.desc())
    )
    result = await db.execute(stmt)
    return [
        {
            "id": item.id,
            "product": ProductOut.model_validate(product).model_dump(mode="json"),
            "shop_name": shop_name,
            "added_at": item.created_at,
        }
        for item, product, shop_name in result.all()
    ]


@router.post("", response_model=WishlistItemOut, status_code=201)
async def add_to_wishlist(
    payload: WishlistAddRequest,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == payload.product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # ON CONFLICT DO NOTHING (the model's UniqueConstraint) rather than a
    # SELECT-then-INSERT check — makes "add to wishlist" naturally
    # idempotent under a double-click or two tabs, with no race window
    # between the check and the insert.
    stmt = (
        pg_insert(WishlistItem)
        .values(id=uuid.uuid4(), user_id=user.id, product_id=product.id)
        .on_conflict_do_nothing(constraint="uq_wishlist_user_product")
        .returning(WishlistItem.id, WishlistItem.created_at)
    )
    inserted = (await db.execute(stmt)).first()
    await db.commit()

    if inserted is None:
        # Already wishlisted — fetch the existing row instead of
        # pretending we just created a second one.
        existing = await db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == user.id, WishlistItem.product_id == product.id
            )
        )
        item = existing.scalar_one()
        item_id, added_at = item.id, item.created_at
    else:
        item_id, added_at = inserted

    shop_result = await db.execute(select(Shop.name).where(Shop.id == product.shop_id))
    shop_name = shop_result.scalar_one_or_none()

    return {
        "id": item_id,
        "product": ProductOut.model_validate(product).model_dump(mode="json"),
        "shop_name": shop_name,
        "added_at": added_at,
    }


@router.delete("/{product_id}")
async def remove_from_wishlist(
    product_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pid = parse_uuid_or_404(product_id, "Product")
    result = await db.execute(
        select(WishlistItem).where(WishlistItem.user_id == user.id, WishlistItem.product_id == pid)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Not in your wishlist")

    await db.delete(item)
    await db.commit()
    return {"product_id": product_id, "removed": True}
