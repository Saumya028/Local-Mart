import uuid
from decimal import Decimal

import razorpay
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cart as cart_store
from app.core.config import settings
from app.core.db import get_db
from app.core.idempotency import idempotent
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Address, Order, OrderItem, Payment, Product, Profile, Shop
from app.schemas.order import CheckoutRequest, CheckoutResponse, OrderDetailOut, OrderOut
from app.schemas.shop import ShopOut

router = APIRouter(tags=["orders"])

razorpay_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


@router.post("/orders", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    The whole checkout flow:

    1. Resolve the chosen address (Phase 4: a saved address, not free
       text) and snapshot it into a formatted string — orders should
       still show the correct address even if the address book entry is
       later edited or deleted.
    2. Read the cart from Redis. Prices and stock are NEVER trusted from
       anywhere but Postgres, checked fresh right here.
    3. Group cart lines by shop — a cart spanning 3 shops becomes 3 Order
       rows (see the Order model's docstring for why).
    4. For each item, atomically reserve stock with a single
       UPDATE ... WHERE stock_qty >= qty ... RETURNING statement — this is
       race-safe (verified in Phase 3 under a simulated concurrent-buyer
       race): two checkouts for the same last unit cannot both succeed.
    5. Create Order + OrderItem rows. Nothing is committed yet.
    6. Create ONE Razorpay Order for the whole cart total, and a Payment
       row per order pointing at it.
    7. Commit everything together, THEN clear the cart.

    Because nothing is committed until step 7, an insufficient-stock
    error on ANY item, a bad address, or the Razorpay API call itself
    failing all roll back the whole attempt — no partial orders, no stock
    decremented for nothing.

    This endpoint only ever creates a "pending" order — actual payment
    confirmation happens asynchronously in the Razorpay webhook.
    """

    async def do_checkout() -> dict:
        address_result = await db.execute(select(Address).where(Address.id == payload.address_id))
        address = address_result.scalar_one_or_none()
        if address is None or address.user_id != user.id:
            raise HTTPException(status_code=404, detail="Address not found")
        delivery_address_snapshot = f"{address.label}: {address.line1}, {address.city}"

        raw_items = await cart_store.get_cart_items(user.id)
        if not raw_items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        product_ids = [uuid.UUID(pid) for pid in raw_items.keys()]
        result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
        products_by_id = {str(p.id): p for p in result.scalars().all()}

        items_by_shop: dict[uuid.UUID, list[tuple[Product, int]]] = {}
        for product_id, qty in raw_items.items():
            product = products_by_id.get(product_id)
            if product is None or not product.is_active:
                raise HTTPException(
                    status_code=400, detail=f"Product {product_id} is no longer available"
                )
            items_by_shop.setdefault(product.shop_id, []).append((product, qty))

        created_orders: list[Order] = []
        grand_total = Decimal("0")

        for shop_id, items in items_by_shop.items():
            order = Order(
                id=uuid.uuid4(),
                user_id=user.id,
                shop_id=shop_id,
                status="pending",
                total_amount=Decimal("0"),  # filled in below once we know the line totals
                delivery_address=delivery_address_snapshot,
            )
            db.add(order)
            await db.flush()  # so order.id is usable as a foreign key on the OrderItems below

            order_total = Decimal("0")
            for product, qty in items:
                stmt = (
                    update(Product)
                    .where(Product.id == product.id, Product.stock_qty >= qty)
                    .values(stock_qty=Product.stock_qty - qty)
                    .returning(Product.id)
                )
                reserved = await db.execute(stmt)
                if reserved.first() is None:
                    raise HTTPException(
                        status_code=409, detail=f'Not enough stock for "{product.name}"'
                    )

                line_total = product.price * qty
                order_total += line_total
                db.add(
                    OrderItem(
                        id=uuid.uuid4(),
                        order_id=order.id,
                        product_id=product.id,
                        quantity=qty,
                        unit_price=product.price,
                    )
                )

            order.total_amount = order_total
            grand_total += order_total
            created_orders.append(order)

        # Razorpay amounts are integers in the smallest currency unit
        # (paise for INR) — hence the *100. This call creates the Order
        # on Razorpay's side (not to be confused with our own Order rows
        # above) that the frontend's Checkout widget opens a payment
        # popup against.
        try:
            razorpay_order = razorpay_client.order.create(
                {
                    "amount": int(grand_total * 100),
                    "currency": "INR",
                    "notes": {
                        "user_id": str(user.id),
                        "order_ids": ",".join(str(o.id) for o in created_orders),
                    },
                }
            )
        except razorpay.errors.BadRequestError as e:
            raise HTTPException(status_code=502, detail=f"Payment provider error: {e}")

        for order in created_orders:
            db.add(
                Payment(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    provider_ref=razorpay_order["id"],
                    status="pending",
                    amount=order.total_amount,
                    method="card",
                )
            )

        await db.commit()
        await cart_store.clear_cart(user.id)

        return {
            "orders": [OrderOut.model_validate(o).model_dump(mode="json") for o in created_orders],
            "razorpay_order_id": razorpay_order["id"],
            "razorpay_key_id": settings.razorpay_key_id,
            "total_amount": str(grand_total),
        }

    idempotency_redis_key = f"idempotency:checkout:{user.id}:{idempotency_key}"
    return await idempotent(idempotency_redis_key, ttl_seconds=86400, action=do_checkout)


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Order history — deliberately lightweight (no line items) since a
    list view only needs enough to identify and link to each order."""
    result = await db.execute(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def get_order(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full order detail for the tracking page: status, shop, and every line
    item. The Checkout page also polls this right after payment, since
    confirmation happens asynchronously via webhook — this is how the
    frontend finds out the webhook actually landed.
    """
    oid = parse_uuid_or_404(order_id, "Order")
    result = await db.execute(select(Order).where(Order.id == oid))
    order = result.scalar_one_or_none()

    # Scoped to the requesting user — a shop owner or another customer
    # must never be able to look up someone else's order by guessing IDs.
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    shop_result = await db.execute(select(Shop).where(Shop.id == order.shop_id))
    shop = shop_result.scalar_one_or_none()

    items_result = await db.execute(
        select(OrderItem, Product.name)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order.id)
    )
    items = [
        {
            "product_name": name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.unit_price * item.quantity,
        }
        for item, name in items_result.all()
    ]

    data = OrderOut.model_validate(order).model_dump(mode="json")
    data["shop"] = ShopOut.model_validate(shop).model_dump(mode="json") if shop else None
    data["items"] = items
    return data
