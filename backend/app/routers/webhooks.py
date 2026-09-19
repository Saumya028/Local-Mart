import json

import razorpay
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.payment_confirmation import mark_payment_captured, mark_payment_failed

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

    This is the source-of-truth confirmation path, but not the only one —
    see core/payment_confirmation.py's docstring for why POST
    /orders/verify-payment also exists and calls the exact same
    mark_payment_captured/mark_payment_failed helpers this does.

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
        if event_type == "payment.captured":
            await mark_payment_captured(db, provider_ref, method=payment_entity.get("method"))
        elif event_type == "payment.failed":
            await mark_payment_failed(db, provider_ref)

        await db.commit()

    return {"received": True}
