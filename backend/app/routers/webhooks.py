import json

import razorpay
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select, update

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models import Order, OrderItem, Payment, Product

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
):
    """
    Razorpay calls this directly (never the frontend) whenever a
    payment's status changes. We verify the signature to make sure the
    request genuinely came from Razorpay — without that check, anyone who
    found this URL could POST a fake "payment captured" event and get an
    order confirmed for free.

    This opens its own database session rather than using the get_db
    dependency, since a webhook's lifecycle is Razorpay's, not a logged-in
    user's request.

    Local dev: use the Razorpay CLI (`razorpay-cli listen`) or a tunnel
    (ngrok/Cloudflare Tunnel) pointed at localhost:8000/webhooks/razorpay,
    and register that URL + the "payment.captured" / "payment.failed"
    events under Dashboard -> Settings -> Webhooks — see the README.
    """
    payload = await request.body()

    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing webhook signature")

    try:
        _client.utility.verify_webhook_signature(
            payload.decode(), x_razorpay_signature, settings.razorpay_webhook_secret
        )
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = json.loads(payload)
    event_type = event.get("event")
    payment_entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    # This is the Razorpay ORDER id (not the payment id) — it's what we
    # stored as Payment.provider_ref back in routers/orders.py, since one
    # Razorpay Order can cover several of our own Order rows at once.
    provider_ref = payment_entity.get("order_id")

    if provider_ref is None:
        # Not a payment event we care about (e.g. refund/dispute webhooks
        # if those get enabled later) — acknowledge and ignore.
        return {"received": True}

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Payment).where(Payment.provider_ref == provider_ref))
        payments = result.scalars().all()

        if event_type == "payment.captured":
            for payment in payments:
                payment.status = "succeeded"
                payment.method = payment_entity.get("method", payment.method)
                await db.execute(
                    update(Order).where(Order.id == payment.order_id).values(status="confirmed")
                )

        elif event_type == "payment.failed":
            for payment in payments:
                payment.status = "failed"
                await db.execute(
                    update(Order).where(Order.id == payment.order_id).values(status="payment_failed")
                )

                # Release the stock reserved at checkout time — this
                # order is never going to be fulfilled, so holding onto
                # that stock would incorrectly block other customers from
                # buying it.
                items_result = await db.execute(
                    select(OrderItem).where(OrderItem.order_id == payment.order_id)
                )
                for item in items_result.scalars().all():
                    await db.execute(
                        update(Product)
                        .where(Product.id == item.product_id)
                        .values(stock_qty=Product.stock_qty + item.quantity)
                    )

        await db.commit()

    return {"received": True}
