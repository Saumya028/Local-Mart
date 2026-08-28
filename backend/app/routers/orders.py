import uuid
from decimal import Decimal

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cart as cart_store
from app.core.config import settings
from app.core.db import get_db
from app.core.idempotency import idempotent
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Order, OrderItem, Payment, Product, Profile
from app.schemas.order import CheckoutRequest, CheckoutResponse, OrderOut

router = APIRouter(tags=["orders"])

stripe.api_key = settings.stripe_secret_key


@router.post("/orders", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    The whole checkout flow:

    1. Read the cart from Redis. Prices and stock are NEVER trusted from
       anywhere but Postgres, checked fresh right here.
    2. Group cart lines by shop — a cart spanning 3 shops becomes 3 Order
       rows (see the Order model's docstring for why).
    3. For each item, atomically reserve stock with a single
       UPDATE ... WHERE stock_qty >= qty ... RETURNING statement. This is
       race-safe: Postgres's row-level locking means two concurrent
       checkouts for the same product physically cannot both succeed past
       the last unit — one's UPDATE will affect 0 rows and fail cleanly.
    4. Create Order + OrderItem rows. Nothing is committed yet.
    5. Create ONE Stripe PaymentIntent for the whole cart total, and a
       Payment row per order pointing at it.
    6. Commit everything together, THEN clear the cart.

    Because nothing is committed until step 6, an insufficient-stock
    error on ANY item — or the Stripe API call itself failing — rolls
    back the whole attempt: no partial orders, no stock decremented for
    nothing. FastAPI's dependency cleanup closes the session on an
    unhandled exception, which rolls back anything uncommitted.

    This endpoint only ever creates a "pending" order — actual payment
    confirmation happens asynchronously in the Stripe webhook below.
    """

    async def do_checkout() -> dict:
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
                delivery_address=payload.delivery_address,
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

        # Stripe amounts are integers in the smallest currency unit
        # (paise for INR) — hence the *100.
        intent = stripe.PaymentIntent.create(
            amount=int(grand_total * 100),
            currency="inr",
            metadata={
                "user_id": str(user.id),
                "order_ids": ",".join(str(o.id) for o in created_orders),
            },
        )

        for order in created_orders:
            db.add(
                Payment(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    provider_ref=intent.id,
                    status="pending",
                    amount=order.total_amount,
                    method="card",
                )
            )

        await db.commit()
        await cart_store.clear_cart(user.id)

        return {
            "orders": [OrderOut.model_validate(o).model_dump(mode="json") for o in created_orders],
            "client_secret": intent.client_secret,
            "total_amount": str(grand_total),
        }

    idempotency_redis_key = f"idempotency:checkout:{user.id}:{idempotency_key}"
    return await idempotent(idempotency_redis_key, ttl_seconds=86400, action=do_checkout)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Minimal order lookup — enough for the Checkout page to poll status
    after payment. Full order history / listing is Phase 4.
    """
    oid = parse_uuid_or_404(order_id, "Order")
    result = await db.execute(select(Order).where(Order.id == oid))
    order = result.scalar_one_or_none()

    # Scoped to the requesting user — a shop owner or another customer
    # must never be able to look up someone else's order by guessing IDs.
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    return order
