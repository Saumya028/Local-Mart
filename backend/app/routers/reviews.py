"""
Customer + public side of the review system: read a product's or shop's
reviews (anyone), and write/edit/delete your own (verified buyers only).
The shop owner's side — replying and hiding — lives in
routers/shop_reviews.py.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.order_status import TERMINAL_STATUSES
from app.core.rate_limit import rate_limit_by_user
from app.core.reviews import (
    REVIEW_WRITE_LIMIT,
    REVIEW_WRITE_WINDOW_SECONDS,
    has_fulfilled_product_order,
    has_fulfilled_shop_order,
    invalidate_product_caches,
    invalidate_shop_caches,
    mask_reviewer_name,
    rating_stats,
    recompute_product_rating,
    recompute_shop_rating,
)
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Order, OrderItem, Product, ProductReview, Profile, Shop, ShopReview
from app.schemas.review import (
    MyReviewOut,
    MyReviewsOut,
    PendingProduct,
    PendingShop,
    ReviewCreate,
    ReviewEligibility,
    ReviewListOut,
    ReviewOut,
)

router = APIRouter(tags=["reviews"])

WriteUser = Depends(rate_limit_by_user("review_write", REVIEW_WRITE_LIMIT, REVIEW_WRITE_WINDOW_SECONDS))

SortKey = Literal["recent", "highest", "lowest"]


@dataclass(frozen=True)
class _Kind:
    """What differs between a product review and a shop review."""

    name: str
    model: type
    target_column: object  # the model's product_id / shop_id column
    not_found: str


PRODUCT = _Kind("product", ProductReview, ProductReview.product_id, "Product")
SHOP = _Kind("shop", ShopReview, ShopReview.shop_id, "Shop")


def _public(review, reviewer_name: str | None) -> dict:
    return ReviewOut(
        id=review.id,
        rating=review.rating,
        title=review.title,
        body=review.body,
        reviewer_name=mask_reviewer_name(reviewer_name),
        created_at=review.created_at,
        edited_at=review.edited_at,
        reply_text=review.reply_text,
        replied_at=review.replied_at,
    ).model_dump(mode="json")


async def _my_review_out(db: AsyncSession, kind: _Kind, review, user: Profile) -> MyReviewOut:
    if kind is PRODUCT:
        row = (
            await db.execute(select(Product.name, Product.images).where(Product.id == review.product_id))
        ).first()
        name, image = (row[0], (row[1] or [None])[0]) if row else (None, None)
        product_id = review.product_id
    else:
        name = (await db.execute(select(Shop.name).where(Shop.id == review.shop_id))).scalar_one_or_none()
        image, product_id = None, None
    return MyReviewOut(
        id=review.id,
        rating=review.rating,
        title=review.title,
        body=review.body,
        reviewer_name=mask_reviewer_name(user.full_name),
        created_at=review.created_at,
        edited_at=review.edited_at,
        reply_text=review.reply_text,
        replied_at=review.replied_at,
        kind=kind.name,
        product_id=product_id,
        shop_id=review.shop_id,
        target_name=name,
        target_image=image,
        is_hidden=review.is_hidden,
    )


async def _require_target(db: AsyncSession, kind: _Kind, target_id: str) -> uuid.UUID:
    tid = parse_uuid_or_404(target_id, kind.not_found)
    target = Product if kind is PRODUCT else Shop
    found = (await db.execute(select(target.id).where(target.id == tid))).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=404, detail=f"{kind.not_found} not found")
    return tid


async def _list_reviews(
    db: AsyncSession, kind: _Kind, tid: uuid.UUID, sort: SortKey, rating: int | None, limit: int, offset: int
) -> dict:
    model = kind.model
    where = [kind.target_column == tid, model.is_hidden.is_(False)]
    if rating is not None:
        where.append(model.rating == rating)

    order = {
        "recent": [model.created_at.desc()],
        "highest": [model.rating.desc(), model.created_at.desc()],
        "lowest": [model.rating.asc(), model.created_at.desc()],
    }[sort]

    rows = (
        await db.execute(
            select(model, Profile.full_name)
            .join(Profile, Profile.id == model.user_id)
            .where(*where)
            .order_by(*order)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = (await db.execute(select(func.count()).select_from(model).where(*where))).scalar_one()
    return {
        "summary": await rating_stats(db, model, kind.target_column, tid),
        "items": [_public(r, name) for r, name in rows],
        "total": int(total),
    }


async def _eligibility(db: AsyncSession, kind: _Kind, tid: uuid.UUID, user: Profile) -> ReviewEligibility:
    review = (
        await db.execute(select(kind.model).where(kind.model.user_id == user.id, kind.target_column == tid))
    ).scalar_one_or_none()
    if review is not None:
        return ReviewEligibility(can_review=True, review=await _my_review_out(db, kind, review, user))
    bought = (
        await has_fulfilled_product_order(db, user.id, tid)
        if kind is PRODUCT
        else await has_fulfilled_shop_order(db, user.id, tid)
    )
    if bought:
        return ReviewEligibility(can_review=True)
    return ReviewEligibility(
        can_review=False,
        reason=f"Only customers who received an order from this {kind.name} can review it.",
    )


async def _create(db: AsyncSession, kind: _Kind, tid: uuid.UUID, payload: ReviewCreate, user: Profile):
    existing = (
        await db.execute(
            select(kind.model.id).where(kind.model.user_id == user.id, kind.target_column == tid)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="You've already reviewed this — edit your review instead.")

    if kind is PRODUCT:
        if not await has_fulfilled_product_order(db, user.id, tid):
            raise HTTPException(
                status_code=403, detail="You can review a product once an order containing it has been delivered."
            )
        shop_id = (await db.execute(select(Product.shop_id).where(Product.id == tid))).scalar_one()
        review = ProductReview(id=uuid.uuid4(), user_id=user.id, product_id=tid, shop_id=shop_id)
    else:
        if not await has_fulfilled_shop_order(db, user.id, tid):
            raise HTTPException(
                status_code=403, detail="You can review a shop once an order from it has been delivered."
            )
        review = ShopReview(id=uuid.uuid4(), user_id=user.id, shop_id=tid)

    review.rating, review.title, review.body = payload.rating, payload.title, payload.body
    db.add(review)
    try:
        await db.flush()
    except IntegrityError:
        # Lost a race with a double-click / second tab: the unique
        # constraint is the real guard, the SELECT above is just the
        # friendly path.
        await db.rollback()
        raise HTTPException(status_code=409, detail="You've already reviewed this — edit your review instead.")
    await _after_write(db, kind, tid)
    await db.commit()
    await _invalidate(kind, tid)
    return review


async def _after_write(db: AsyncSession, kind: _Kind, tid: uuid.UUID) -> None:
    if kind is PRODUCT:
        await recompute_product_rating(db, tid)
    else:
        await recompute_shop_rating(db, tid)


async def _invalidate(kind: _Kind, tid: uuid.UUID) -> None:
    if kind is PRODUCT:
        await invalidate_product_caches(tid)
    else:
        await invalidate_shop_caches(tid)


async def _load_mine(db: AsyncSession, kind: _Kind, tid: uuid.UUID, user: Profile):
    review = (
        await db.execute(select(kind.model).where(kind.model.user_id == user.id, kind.target_column == tid))
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="You haven't reviewed this yet")
    return review


# ---------------------------------------------------------------- products


@router.get("/products/{product_id}/reviews", response_model=ReviewListOut)
async def list_product_reviews(
    product_id: str,
    sort: SortKey = Query(default="recent"),
    rating: int | None = Query(default=None, ge=1, le=5),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    tid = await _require_target(db, PRODUCT, product_id)
    return await _list_reviews(db, PRODUCT, tid, sort, rating, limit, offset)


@router.get("/products/{product_id}/reviews/mine", response_model=ReviewEligibility)
async def my_product_review(
    product_id: str, user: Profile = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    tid = await _require_target(db, PRODUCT, product_id)
    return await _eligibility(db, PRODUCT, tid, user)


@router.post("/products/{product_id}/reviews", response_model=MyReviewOut, status_code=201)
async def create_product_review(
    product_id: str, payload: ReviewCreate, user: Profile = WriteUser, db: AsyncSession = Depends(get_db)
):
    tid = await _require_target(db, PRODUCT, product_id)
    review = await _create(db, PRODUCT, tid, payload, user)
    return await _my_review_out(db, PRODUCT, review, user)


@router.put("/products/{product_id}/reviews/mine", response_model=MyReviewOut)
async def update_product_review(
    product_id: str, payload: ReviewCreate, user: Profile = WriteUser, db: AsyncSession = Depends(get_db)
):
    tid = await _require_target(db, PRODUCT, product_id)
    review = await _load_mine(db, PRODUCT, tid, user)
    review.rating, review.title, review.body = payload.rating, payload.title, payload.body
    review.edited_at = datetime.now(timezone.utc)
    await recompute_product_rating(db, tid)
    await db.commit()
    await invalidate_product_caches(tid)
    return await _my_review_out(db, PRODUCT, review, user)


@router.delete("/products/{product_id}/reviews/mine")
async def delete_product_review(
    product_id: str, user: Profile = WriteUser, db: AsyncSession = Depends(get_db)
):
    tid = await _require_target(db, PRODUCT, product_id)
    review = await _load_mine(db, PRODUCT, tid, user)
    await db.delete(review)
    await db.flush()
    await recompute_product_rating(db, tid)
    await db.commit()
    await invalidate_product_caches(tid)
    return {"deleted": True}


# ------------------------------------------------------------------- shops


@router.get("/shops/{shop_id}/reviews", response_model=ReviewListOut)
async def list_shop_reviews(
    shop_id: str,
    sort: SortKey = Query(default="recent"),
    rating: int | None = Query(default=None, ge=1, le=5),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    tid = await _require_target(db, SHOP, shop_id)
    return await _list_reviews(db, SHOP, tid, sort, rating, limit, offset)


@router.get("/shops/{shop_id}/reviews/mine", response_model=ReviewEligibility)
async def my_shop_review(
    shop_id: str, user: Profile = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    tid = await _require_target(db, SHOP, shop_id)
    return await _eligibility(db, SHOP, tid, user)


@router.post("/shops/{shop_id}/reviews", response_model=MyReviewOut, status_code=201)
async def create_shop_review(
    shop_id: str, payload: ReviewCreate, user: Profile = WriteUser, db: AsyncSession = Depends(get_db)
):
    tid = await _require_target(db, SHOP, shop_id)
    review = await _create(db, SHOP, tid, payload, user)
    return await _my_review_out(db, SHOP, review, user)


@router.put("/shops/{shop_id}/reviews/mine", response_model=MyReviewOut)
async def update_shop_review(
    shop_id: str, payload: ReviewCreate, user: Profile = WriteUser, db: AsyncSession = Depends(get_db)
):
    tid = await _require_target(db, SHOP, shop_id)
    review = await _load_mine(db, SHOP, tid, user)
    review.rating, review.title, review.body = payload.rating, payload.title, payload.body
    review.edited_at = datetime.now(timezone.utc)
    await recompute_shop_rating(db, tid)
    await db.commit()
    await invalidate_shop_caches(tid)
    return await _my_review_out(db, SHOP, review, user)


@router.delete("/shops/{shop_id}/reviews/mine")
async def delete_shop_review(shop_id: str, user: Profile = WriteUser, db: AsyncSession = Depends(get_db)):
    tid = await _require_target(db, SHOP, shop_id)
    review = await _load_mine(db, SHOP, tid, user)
    await db.delete(review)
    await db.flush()
    await recompute_shop_rating(db, tid)
    await db.commit()
    await invalidate_shop_caches(tid)
    return {"deleted": True}


# ------------------------------------------------------------ My Account


@router.get("/reviews/mine", response_model=MyReviewsOut)
async def my_reviews(user: Profile = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    My Account > My Reviews: everything I've written, plus what I could
    still review — products/shops from orders that reached me and that I
    haven't reviewed yet.
    """
    reviews: list[MyReviewOut] = []
    for kind in (PRODUCT, SHOP):
        rows = (
            await db.execute(
                select(kind.model).where(kind.model.user_id == user.id).order_by(kind.model.created_at.desc())
            )
        ).scalars().all()
        for r in rows:
            reviews.append(await _my_review_out(db, kind, r, user))
    reviews.sort(key=lambda r: r.created_at, reverse=True)

    # Most recent fulfilled order per product / shop that has no review yet.
    product_rows = (
        await db.execute(
            select(
                Product.id,
                Product.name,
                Product.images,
                Shop.name,
                func.max(Order.delivered_at).label("last"),
                func.max(Order.id.cast(String)).label("order_id"),
            )
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
            .join(Shop, Shop.id == Product.shop_id)
            .where(
                Order.user_id == user.id,
                Order.status.in_(TERMINAL_STATUSES),
                ~exists().where(ProductReview.user_id == user.id, ProductReview.product_id == Product.id),
            )
            .group_by(Product.id, Product.name, Product.images, Shop.name)
            .order_by(func.max(Order.delivered_at).desc().nullslast())
            .limit(20)
        )
    ).all()
    shop_rows = (
        await db.execute(
            select(
                Shop.id,
                Shop.name,
                func.max(Order.delivered_at).label("last"),
                func.max(Order.id.cast(String)).label("order_id"),
            )
            .select_from(Order)
            .join(Shop, Shop.id == Order.shop_id)
            .where(
                Order.user_id == user.id,
                Order.status.in_(TERMINAL_STATUSES),
                ~exists().where(ShopReview.user_id == user.id, ShopReview.shop_id == Shop.id),
            )
            .group_by(Shop.id, Shop.name)
            .order_by(func.max(Order.delivered_at).desc().nullslast())
            .limit(20)
        )
    ).all()

    return MyReviewsOut(
        reviews=reviews,
        pending_products=[
            PendingProduct(
                product_id=pid,
                product_name=pname,
                image=(images or [None])[0],
                shop_name=sname,
                order_id=uuid.UUID(oid),
            )
            for pid, pname, images, sname, _last, oid in product_rows
        ],
        pending_shops=[
            PendingShop(shop_id=sid, shop_name=sname, order_id=uuid.UUID(oid))
            for sid, sname, _last, oid in shop_rows
        ],
    )
