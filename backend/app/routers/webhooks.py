import stripe
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select, update

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models import Order, OrderItem, Payment, Product

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
):
    """
    Stripe calls this directly (never the frontend) whenever a payment's
    status changes. We verify the signature to make sure the request
    genuinely came from Stripe — without that check, anyone who found
    this URL could POST a fake "payment succeeded" event and get an order
    confirmed for free.

    This opens its own database session rather than using the get_db
    dependency, since a webhook's lifecycle is Stripe's, not a logged-in
    user's request.

    Local dev: run `stripe listen --forward-to localhost:8000/webhooks/stripe`
    (Stripe CLI) to receive these events on your machine — see the README.
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    intent = event["data"]["object"]
    provider_ref = intent["id"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Payment).where(Payment.provider_ref == provider_ref))
        payments = result.scalars().all()

        if event["type"] == "payment_intent.succeeded":
            for payment in payments:
                payment.status = "succeeded"
                await db.execute(
                    update(Order).where(Order.id == payment.order_id).values(status="confirmed")
                )

        elif event["type"] == "payment_intent.payment_failed":
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
