import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cart as cart_store
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Product, Profile
from app.schemas.product import ProductOut

router = APIRouter(prefix="/cart", tags=["cart"])


class AddToCartRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = 1


class SetQuantityRequest(BaseModel):
    quantity: int


@router.get("")
async def get_cart(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the cart already enriched with product details and a total —
    the frontend gets everything it needs to render the Cart page in one
    call, rather than fetching raw {product_id: quantity} and then
    looking up each product itself.

    Quantities live in Redis; product details (name, current price, stock)
    are always read fresh from Postgres here — never cached alongside the
    cart itself, since a stale price shown in the cart would be
    misleading (checkout re-validates price anyway, but the cart view
    shouldn't disagree with it either).
    """
    raw_items = await cart_store.get_cart_items(user.id)
    if not raw_items:
        return {"items": [], "total": "0.00"}

    product_ids = [uuid.UUID(pid) for pid in raw_items.keys()]
    result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
    products_by_id = {str(p.id): p for p in result.scalars().all()}

    items = []
    total = 0
    for product_id, qty in raw_items.items():
        product = products_by_id.get(product_id)
        if product is None:
            # Product was deleted/deactivated after being added to the
            # cart — drop it silently rather than breaking the cart page.
            continue
        subtotal = product.price * qty
        total += subtotal
        items.append(
            {
                "product": ProductOut.model_validate(product).model_dump(mode="json"),
                "quantity": qty,
                "subtotal": str(subtotal),
            }
        )

    return {"items": items, "total": str(total)}


@router.post("/items")
async def add_item(
    payload: AddToCartRequest,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(Product.id == payload.product_id, Product.is_active.is_(True))
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Deliberately NOT checking stock strictly here — a cheap "does it
    # exist and is it active" check is enough at add-to-cart time. Stock
    # is re-validated properly, against the real number, at checkout.
    new_qty = await cart_store.add_to_cart(user.id, str(payload.product_id), payload.quantity)
    return {"product_id": str(payload.product_id), "quantity": new_qty}


@router.put("/items/{product_id}")
async def set_item_quantity(
    product_id: str,
    payload: SetQuantityRequest,
    user: Profile = Depends(get_current_user),
):
    await cart_store.set_cart_item(user.id, product_id, payload.quantity)
    return {"product_id": product_id, "quantity": max(payload.quantity, 0)}


@router.delete("/items/{product_id}")
async def remove_item(product_id: str, user: Profile = Depends(get_current_user)):
    await cart_store.remove_from_cart(user.id, product_id)
    return {"product_id": product_id, "removed": True}
