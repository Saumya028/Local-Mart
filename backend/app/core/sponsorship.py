"""Payment + activation helpers for sponsorship purchases.

The platform never trusts the browser's claim that "I paid": a purchase is
only activated after (a) Razorpay's checkout signature verifies against
our secret, or (b) Razorpay's own server-to-server webhook verifies. Both
paths call activate_purchase(), which is idempotent, so a buyer whose
browser confirm AND webhook both arrive gets exactly one extension.
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Shop, SponsorshipPurchase


def payment_mode() -> str | None:
    """"razorpay" with keys set; "test" for local dev without keys;
    None (buying disabled) in production without keys."""
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        return "razorpay"
    if settings.environment != "production":
        return "test"
    return None


async def create_razorpay_order(amount_paise: int, receipt: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            "https://api.razorpay.com/v1/orders",
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            json={"amount": amount_paise, "currency": "INR", "receipt": receipt[:40]},
        )
    res.raise_for_status()
    return res.json()


def verify_checkout_signature(order_id: str, payment_id: str, signature: str) -> bool:
    expected = hmac.new(
        settings.razorpay_key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    if not settings.razorpay_webhook_secret:
        return False
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


async def activate_purchase(db: AsyncSession, purchase_id, payment_id: str | None) -> SponsorshipPurchase | None:
    """Mark a purchase paid and extend its shop's sponsorship. Safe to
    call twice. Row-locks the purchase and the shop so a confirm call and
    a webhook racing each other cannot both extend. Caller commits."""
    purchase = (
        await db.execute(
            select(SponsorshipPurchase).where(SponsorshipPurchase.id == purchase_id).with_for_update()
        )
    ).scalar_one_or_none()
    if purchase is None:
        return None
    if purchase.status == "paid":
        return purchase

    shop = (await db.execute(select(Shop).where(Shop.id == purchase.shop_id).with_for_update())).scalar_one()
    now = datetime.now(timezone.utc)
    # Renewing while still sponsored stacks onto the remaining time.
    start = shop.sponsored_until if (shop.sponsored_until and shop.sponsored_until > now) else now
    end = start + timedelta(days=purchase.days)

    shop.sponsored_until = end
    purchase.status = "paid"
    purchase.provider_payment_id = payment_id
    purchase.starts_at = start
    purchase.ends_at = end
    purchase.paid_at = now
    return purchase


async def activate_banner_payment(db: AsyncSession, payment_id, provider_payment_id: str | None):
    """Banner counterpart of activate_purchase(): idempotent, row-locked,
    extends Banner.ends_at (stacking on the remaining time if the banner
    is still live, so renewing early loses nothing). Caller commits."""
    from app.models import Banner, BannerPayment

    payment = (
        await db.execute(select(BannerPayment).where(BannerPayment.id == payment_id).with_for_update())
    ).scalar_one_or_none()
    if payment is None:
        return None
    if payment.status == "paid":
        return payment

    banner = (await db.execute(select(Banner).where(Banner.id == payment.banner_id).with_for_update())).scalar_one()
    now = datetime.now(timezone.utc)
    still_live = banner.ends_at is not None and banner.ends_at > now
    start = banner.ends_at if still_live else now
    end = start + timedelta(days=payment.days)

    if not still_live:
        banner.starts_at = now
    banner.ends_at = end
    payment.status = "paid"
    payment.provider_payment_id = provider_payment_id
    payment.starts_at = start
    payment.ends_at = end
    payment.paid_at = now
    return payment
