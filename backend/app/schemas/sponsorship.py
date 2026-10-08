import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    days: int
    price: Decimal
    is_active: bool


class PlansResponse(BaseModel):
    # "razorpay" | "test" | None (None = buying disabled on this server)
    mode: str | None
    razorpay_key_id: str | None = None
    plans: list[PlanOut]


class CheckoutRequest(BaseModel):
    plan_key: str


class CheckoutResponse(BaseModel):
    purchase_id: uuid.UUID
    mode: str
    amount: Decimal
    plan_name: str
    # Razorpay only:
    razorpay_key_id: str | None = None
    razorpay_order_id: str | None = None
    amount_paise: int | None = None


class ConfirmRequest(BaseModel):
    purchase_id: uuid.UUID
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_name: str
    days: int
    amount: Decimal
    status: str
    provider: str
    starts_at: datetime | None
    ends_at: datetime | None
    paid_at: datetime | None
    created_at: datetime


class SponsorshipStatus(BaseModel):
    is_sponsored: bool
    sponsored_until: datetime | None
    purchases: list[PurchaseOut]


class PlanUpdate(BaseModel):
    name: str | None = None
    price: Decimal | None = None
    is_active: bool | None = None


class AdminPurchaseOut(PurchaseOut):
    shop_id: uuid.UUID
    shop_name: str
    owner_email: str | None


class AdminSponsorshipSummary(BaseModel):
    active_shops: int
    total_shops: int
    paid_purchases: int
    revenue: Decimal
    purchases: list[AdminPurchaseOut]
