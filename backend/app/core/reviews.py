"""
Shared rules for product/shop reviews, used by routers/reviews.py (the
customer + public side) and routers/shop_reviews.py (the shop owner side)
so the two never drift apart on who may review or how averages are made.

Eligibility mirrors the return flow: a customer may only review what has
actually reached them — an order in a TERMINAL status ("delivered" or
"picked_up", see app/core/order_status.py).
"""

import uuid

from sqlalchemy import exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.order_status import TERMINAL_STATUSES
from app.models import Order, OrderItem, Product, ProductReview, Shop, ShopReview

MIN_RATING = 1
MAX_RATING = 5
MAX_TITLE_LEN = 120
MAX_BODY_LEN = 2000
MAX_REPLY_LEN = 1000
MAX_HIDE_REASON_LEN = 300

# Writes are rate-limited per user (see routers/reviews.py).
REVIEW_WRITE_LIMIT = 20
REVIEW_WRITE_WINDOW_SECONDS = 3600


def mask_reviewer_name(full_name: str | None) -> str:
    """
    "Priya Sharma" -> "Priya S."; one-word names stay as-is; no name at
    all -> "LocalMart customer". Reviews are public, so this is the ONLY
    identity they ever carry — never the email or phone.
    """
    parts = (full_name or "").split()
    if not parts:
        return "LocalMart customer"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."


def build_summary(avg: float | None, count: int, distribution: dict[int, int]) -> dict:
    """The shape every summary endpoint returns: average (1 decimal),
    total count, and a count for each star 5..1 (zeros included so the
    UI never has to fill gaps)."""
    return {
        "average": round(float(avg or 0), 1),
        "count": int(count),
        "distribution": {str(star): int(distribution.get(star, 0)) for star in range(MAX_RATING, MIN_RATING - 1, -1)},
    }


async def has_fulfilled_product_order(db: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID) -> bool:
    stmt = select(
        exists().where(
            Order.user_id == user_id,
            Order.status.in_(TERMINAL_STATUSES),
            OrderItem.order_id == Order.id,
            OrderItem.product_id == product_id,
        )
    )
    return bool((await db.execute(stmt)).scalar())


async def has_fulfilled_shop_order(db: AsyncSession, user_id: uuid.UUID, shop_id: uuid.UUID) -> bool:
    stmt = select(
        exists().where(
            Order.user_id == user_id,
            Order.shop_id == shop_id,
            Order.status.in_(TERMINAL_STATUSES),
        )
    )
    return bool((await db.execute(stmt)).scalar())


async def rating_stats(db: AsyncSession, model, column, target_id: uuid.UUID) -> dict:
    """Average, count and per-star counts over a target's VISIBLE reviews."""
    result = await db.execute(
        select(model.rating, func.count())
        .where(column == target_id, model.is_hidden.is_(False))
        .group_by(model.rating)
    )
    distribution = {int(rating): int(n) for rating, n in result.all()}
    count = sum(distribution.values())
    avg = sum(r * n for r, n in distribution.items()) / count if count else 0.0
    return build_summary(avg, count, distribution)


async def recompute_product_rating(db: AsyncSession, product_id: uuid.UUID) -> None:
    """Re-derives products.rating_avg/rating_count from scratch (never
    incrementally — a full recompute can't drift, whatever sequence of
    create/edit/delete/hide happened). Runs in the caller's transaction."""
    stats = await rating_stats(db, ProductReview, ProductReview.product_id, product_id)
    await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(rating_avg=stats["average"], rating_count=stats["count"])
    )


async def recompute_shop_rating(db: AsyncSession, shop_id: uuid.UUID) -> None:
    stats = await rating_stats(db, ShopReview, ShopReview.shop_id, shop_id)
    await db.execute(
        update(Shop).where(Shop.id == shop_id).values(rating=stats["average"], rating_count=stats["count"])
    )


async def invalidate_product_caches(product_id: uuid.UUID) -> None:
    await invalidate(f"product:{product_id}")


async def invalidate_shop_caches(shop_id: uuid.UUID) -> None:
    # The unfiltered shops list is sorted by rating, so it goes stale too.
    await invalidate(f"shop:{shop_id}", "shops:list")
