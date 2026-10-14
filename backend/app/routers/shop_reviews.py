"""
Shop owner side of the review system — everything under
/dashboard/reviews. Owners (and admins, and the shop's managers) can see
every product and shop review for their shop, reply publicly, and hide or
unhide a review. Access reuses the dashboard's own shop-scoping helpers so
the permission rules can't drift from the rest of the dashboard.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.reviews import (
    invalidate_product_caches,
    invalidate_shop_caches,
    mask_reviewer_name,
    rating_stats,
    recompute_product_rating,
    recompute_shop_rating,
)
from app.core.security import require_role
from app.core.utils import parse_uuid_or_404
from app.models import Product, ProductReview, Profile, ShopReview
from app.routers.shop_dashboard import _get_accessible_shop_or_403, _require_approved_shop
from app.schemas.review import (
    DashboardReviewListOut,
    DashboardReviewOut,
    DashboardReviewSummary,
    ReplyRequest,
    VisibilityRequest,
)

# delivery_partner is deliberately absent: their whole job is Orders.
ReviewManager = require_role("shop_owner", "admin", "manager")

router = APIRouter(prefix="/dashboard/reviews", tags=["dashboard-reviews"])

KindFilter = Literal["all", "product", "shop"]
StatusFilter = Literal["all", "unreplied", "replied", "hidden"]


async def _shop_for(db: AsyncSession, shop_id: str, user: Profile):
    sid = parse_uuid_or_404(shop_id, "Shop")
    shop = await _get_accessible_shop_or_403(sid, user, db)
    _require_approved_shop(shop)
    return shop


def _model_for(kind: str):
    if kind == "product":
        return ProductReview
    if kind == "shop":
        return ShopReview
    raise HTTPException(status_code=404, detail="Review not found")


async def _load_review(db: AsyncSession, kind: str, review_id: str, user: Profile):
    """The review, only if it belongs to a shop this user can manage — a
    guessed id for someone else's review is a plain 404/403, never data."""
    model = _model_for(kind)
    rid = parse_uuid_or_404(review_id, "Review")
    review = (await db.execute(select(model).where(model.id == rid))).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    shop = await _get_accessible_shop_or_403(review.shop_id, user, db)
    _require_approved_shop(shop)
    return review


def _status_clauses(model, status: str) -> list:
    if status == "unreplied":
        return [model.reply_text.is_(None), model.is_hidden.is_(False)]
    if status == "replied":
        return [model.reply_text.isnot(None)]
    if status == "hidden":
        return [model.is_hidden.is_(True)]
    return []


def _out(kind: str, review, reviewer_name: str | None, product_name: str | None = None) -> DashboardReviewOut:
    return DashboardReviewOut(
        id=review.id,
        kind=kind,
        rating=review.rating,
        title=review.title,
        body=review.body,
        reviewer_name=mask_reviewer_name(reviewer_name),
        created_at=review.created_at,
        edited_at=review.edited_at,
        reply_text=review.reply_text,
        replied_at=review.replied_at,
        product_id=getattr(review, "product_id", None),
        product_name=product_name,
        is_hidden=review.is_hidden,
        hidden_reason=review.hidden_reason,
        hidden_at=review.hidden_at,
    )


@router.get("", response_model=DashboardReviewListOut)
async def list_reviews(
    shop_id: str,
    kind: KindFilter = Query(default="all"),
    status: StatusFilter = Query(default="all"),
    rating: int | None = Query(default=None, ge=1, le=5),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: Profile = Depends(ReviewManager),
    db: AsyncSession = Depends(get_db),
):
    """
    Product and shop reviews merged newest-first. Each kind is queried
    with limit+offset rows and the two sorted lists are merged in Python —
    exact for a merge of two sorted streams, and avoids a UNION over two
    differently-shaped tables.
    """
    shop = await _shop_for(db, shop_id, user)

    entries: list[tuple[datetime, DashboardReviewOut]] = []
    total = 0
    for k in ("product", "shop"):
        if kind not in ("all", k):
            continue
        model = _model_for(k)
        where = [model.shop_id == shop.id, *_status_clauses(model, status)]
        if rating is not None:
            where.append(model.rating == rating)
        total += (await db.execute(select(func.count()).select_from(model).where(*where))).scalar_one()

        if k == "product":
            rows = (
                await db.execute(
                    select(model, Profile.full_name, Product.name)
                    .join(Profile, Profile.id == model.user_id)
                    .join(Product, Product.id == model.product_id)
                    .where(*where)
                    .order_by(model.created_at.desc())
                    .limit(offset + limit)
                )
            ).all()
            entries += [(r.created_at, _out(k, r, name, pname)) for r, name, pname in rows]
        else:
            rows = (
                await db.execute(
                    select(model, Profile.full_name)
                    .join(Profile, Profile.id == model.user_id)
                    .where(*where)
                    .order_by(model.created_at.desc())
                    .limit(offset + limit)
                )
            ).all()
            entries += [(r.created_at, _out(k, r, name)) for r, name in rows]

    entries.sort(key=lambda e: e[0], reverse=True)
    return DashboardReviewListOut(items=[e[1] for e in entries[offset : offset + limit]], total=int(total))


@router.get("/summary", response_model=DashboardReviewSummary)
async def reviews_summary(
    shop_id: str,
    user: Profile = Depends(ReviewManager),
    db: AsyncSession = Depends(get_db),
):
    shop = await _shop_for(db, shop_id, user)
    unreplied = 0
    hidden = 0
    for model in (ProductReview, ShopReview):
        unreplied += (
            await db.execute(
                select(func.count())
                .select_from(model)
                .where(model.shop_id == shop.id, model.reply_text.is_(None), model.is_hidden.is_(False))
            )
        ).scalar_one()
        hidden += (
            await db.execute(
                select(func.count()).select_from(model).where(model.shop_id == shop.id, model.is_hidden.is_(True))
            )
        ).scalar_one()
    return DashboardReviewSummary(
        shop=await rating_stats(db, ShopReview, ShopReview.shop_id, shop.id),
        products=await rating_stats(db, ProductReview, ProductReview.shop_id, shop.id),
        unreplied_count=int(unreplied),
        hidden_count=int(hidden),
    )


async def _reload_out(db: AsyncSession, kind: str, review) -> DashboardReviewOut:
    name = (await db.execute(select(Profile.full_name).where(Profile.id == review.user_id))).scalar_one_or_none()
    pname = None
    if kind == "product":
        pname = (await db.execute(select(Product.name).where(Product.id == review.product_id))).scalar_one_or_none()
    return _out(kind, review, name, pname)


@router.put("/{kind}/{review_id}/reply", response_model=DashboardReviewOut)
async def reply_to_review(
    kind: Literal["product", "shop"],
    review_id: str,
    payload: ReplyRequest,
    user: Profile = Depends(ReviewManager),
    db: AsyncSession = Depends(get_db),
):
    review = await _load_review(db, kind, review_id, user)
    review.reply_text = payload.text
    review.replied_at = datetime.now(timezone.utc)
    review.replied_by = user.id
    await db.commit()
    await _bust(kind, review)
    return await _reload_out(db, kind, review)


@router.delete("/{kind}/{review_id}/reply", response_model=DashboardReviewOut)
async def delete_reply(
    kind: Literal["product", "shop"],
    review_id: str,
    user: Profile = Depends(ReviewManager),
    db: AsyncSession = Depends(get_db),
):
    review = await _load_review(db, kind, review_id, user)
    review.reply_text = None
    review.replied_at = None
    review.replied_by = None
    await db.commit()
    await _bust(kind, review)
    return await _reload_out(db, kind, review)


@router.patch("/{kind}/{review_id}/visibility", response_model=DashboardReviewOut)
async def set_visibility(
    kind: Literal["product", "shop"],
    review_id: str,
    payload: VisibilityRequest,
    user: Profile = Depends(ReviewManager),
    db: AsyncSession = Depends(get_db),
):
    """
    Hide or restore a review. Hiding needs a reason and removes the review
    from the public list AND the average; who/when/why stay on the row.
    """
    review = await _load_review(db, kind, review_id, user)
    if payload.hidden:
        if not payload.reason:
            raise HTTPException(status_code=400, detail="Give a reason for hiding this review")
        review.is_hidden = True
        review.hidden_reason = payload.reason
        review.hidden_at = datetime.now(timezone.utc)
        review.hidden_by = user.id
    else:
        review.is_hidden = False
        review.hidden_reason = None
        review.hidden_at = None
        review.hidden_by = None

    await db.flush()
    if kind == "product":
        await recompute_product_rating(db, review.product_id)
    else:
        await recompute_shop_rating(db, review.shop_id)
    await db.commit()
    await _bust(kind, review)
    return await _reload_out(db, kind, review)


async def _bust(kind: str, review) -> None:
    if kind == "product":
        await invalidate_product_caches(review.product_id)
    else:
        await invalidate_shop_caches(review.shop_id)
