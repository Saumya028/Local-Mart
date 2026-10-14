import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.reviews import (
    MAX_BODY_LEN,
    MAX_HIDE_REASON_LEN,
    MAX_RATING,
    MAX_REPLY_LEN,
    MAX_TITLE_LEN,
    MIN_RATING,
)


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class ReviewCreate(BaseModel):
    """Used for both creating and editing one's own review."""

    rating: int = Field(ge=MIN_RATING, le=MAX_RATING)
    title: str | None = Field(default=None, max_length=MAX_TITLE_LEN)
    body: str | None = Field(default=None, max_length=MAX_BODY_LEN)

    @field_validator("title", "body")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        return _clean(v)


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_REPLY_LEN)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Reply can't be empty")
        return v


class VisibilityRequest(BaseModel):
    hidden: bool
    # Required when hiding (so a hide is never unexplained); ignored on unhide.
    reason: str | None = Field(default=None, max_length=MAX_HIDE_REASON_LEN)

    @field_validator("reason")
    @classmethod
    def blank_reason(cls, v: str | None) -> str | None:
        return _clean(v)


class RatingSummary(BaseModel):
    average: float
    count: int
    # "5".."1" -> number of reviews with that many stars
    distribution: dict[str, int]


class ReviewOut(BaseModel):
    """A review as the PUBLIC sees it — masked name, never an email."""

    id: uuid.UUID
    rating: int
    title: str | None = None
    body: str | None = None
    reviewer_name: str
    created_at: datetime
    edited_at: datetime | None = None
    reply_text: str | None = None
    replied_at: datetime | None = None
    # Always true today (only buyers can review) — present so the UI
    # doesn't hardcode that assumption.
    verified_purchase: bool = True


class ReviewListOut(BaseModel):
    summary: RatingSummary
    items: list[ReviewOut]
    total: int


class MyReviewOut(ReviewOut):
    """The reviewer's own review (My Reviews tab / edit form)."""

    kind: str  # "product" | "shop"
    product_id: uuid.UUID | None = None
    shop_id: uuid.UUID
    target_name: str | None = None
    target_image: str | None = None
    is_hidden: bool = False


class ReviewEligibility(BaseModel):
    can_review: bool
    # Why not, when can_review is False and there's no existing review.
    reason: str | None = None
    review: MyReviewOut | None = None


class PendingProduct(BaseModel):
    product_id: uuid.UUID
    product_name: str
    image: str | None = None
    shop_name: str | None = None
    order_id: uuid.UUID


class PendingShop(BaseModel):
    shop_id: uuid.UUID
    shop_name: str
    order_id: uuid.UUID


class MyReviewsOut(BaseModel):
    reviews: list[MyReviewOut]
    pending_products: list[PendingProduct]
    pending_shops: list[PendingShop]


# ---- Shop owner side -------------------------------------------------


class DashboardReviewOut(ReviewOut):
    kind: str  # "product" | "shop"
    product_id: uuid.UUID | None = None
    product_name: str | None = None
    is_hidden: bool = False
    hidden_reason: str | None = None
    hidden_at: datetime | None = None


class DashboardReviewListOut(BaseModel):
    items: list[DashboardReviewOut]
    total: int


class DashboardReviewSummary(BaseModel):
    shop: RatingSummary
    products: RatingSummary
    unreplied_count: int
    hidden_count: int
