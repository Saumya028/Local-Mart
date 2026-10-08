import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    description: str
    width: int
    height: int
    price: Decimal
    duration_days: int
    is_active: bool


class SlotsResponse(BaseModel):
    mode: str | None
    razorpay_key_id: str | None = None
    slots: list[SlotOut]


class SlotUpdate(BaseModel):
    price: Decimal | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)
    is_active: bool | None = None


class BannerCreate(BaseModel):
    slot_key: str
    image_url: str = Field(min_length=8, max_length=2000)
    title: str | None = Field(default=None, max_length=120)


class OwnerBannerOut(BaseModel):
    id: uuid.UUID
    slot_key: str
    slot_name: str
    width: int
    height: int
    price: Decimal
    duration_days: int
    image_url: str
    title: str | None
    state: str  # pending | rejected | awaiting_payment | live | expired
    rejection_reason: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    impressions: int
    clicks: int
    created_at: datetime


class BannerCheckoutResponse(BaseModel):
    payment_id: uuid.UUID
    mode: str
    amount: Decimal
    razorpay_key_id: str | None = None
    razorpay_order_id: str | None = None
    amount_paise: int | None = None


class BannerConfirm(BaseModel):
    payment_id: uuid.UUID
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None


class PublicBannerOut(BaseModel):
    id: uuid.UUID
    image_url: str
    title: str | None
    shop_id: uuid.UUID
    shop_name: str
    width: int
    height: int


class RejectBanner(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class AdminBannerOut(OwnerBannerOut):
    shop_id: uuid.UUID
    shop_name: str
    owner_email: str | None
    review_status: str


class AdminBannersResponse(BaseModel):
    pending_count: int
    live_count: int
    revenue: Decimal
    banners: list[AdminBannerOut]
