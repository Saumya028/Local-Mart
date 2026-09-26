import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.return_status import REQUEST_TYPES


class ReturnRequestCreate(BaseModel):
    order_item_id: uuid.UUID
    request_type: str = "return"
    quantity: int
    reason: str
    comment: str | None = None
    # Required, and only meaningful, when request_type == "exchange" — the
    # replacement product the customer wants instead. Validated against
    # the order item's own shop in routers/returns.py, since a Pydantic
    # validator has no database access.
    exchange_product_id: uuid.UUID | None = None

    @field_validator("request_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in REQUEST_TYPES:
            raise ValueError(f"request_type must be one of {REQUEST_TYPES}")
        return v

    @field_validator("quantity")
    @classmethod
    def _positive_qty(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("reason is required")
        return v[:500]

    @field_validator("comment")
    @classmethod
    def _comment_len(cls, v: str | None) -> str | None:
        return v[:1000] if v else v


class ReturnRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    order_item_id: uuid.UUID
    shop_id: uuid.UUID
    request_type: str
    quantity: int
    reason: str
    comment: str | None
    exchange_product_id: uuid.UUID | None
    refund_amount: Decimal
    status: str
    shop_note: str | None
    created_at: datetime
    resolved_at: datetime | None

    # Exchange price-difference settlement — see ReturnRequest's own
    # comments for what each means. Always 0/False/None for a plain
    # "return", since there's no replacement item to compare against.
    price_difference: Decimal = Decimal("0")
    difference_paid: bool = False
    new_order_id: uuid.UUID | None = None

    # Filled in by each router's join, not stored on the row itself — same
    # pattern as OrderOut.shop_name in schemas/order.py. Left optional so
    # this schema stays reusable from endpoints that don't need every
    # field (e.g. the plain create response has no reason to join Shop).
    product_name: str | None = None
    exchange_product_name: str | None = None
    shop_name: str | None = None
    buyer_name: str | None = None
    buyer_email: str | None = None


class DifferencePaymentResponse(BaseModel):
    """POST /returns/{id}/difference-payment — everything the frontend's
    Razorpay Checkout widget needs to open its popup for the top-up
    amount, the same shape CheckoutResponse gives the main checkout flow
    (see schemas/order.py)."""

    razorpay_order_id: str
    razorpay_key_id: str
    amount: Decimal


class VerifyDifferencePaymentRequest(BaseModel):
    """POST /returns/{id}/verify-difference-payment — the signed proof
    Razorpay's Checkout popup hands back, re-verified server-side exactly
    like schemas/order.py's VerifyPaymentRequest does for a normal
    checkout payment."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class ReturnStatusUpdate(BaseModel):
    """
    PATCH /dashboard/returns/{id}/status. `status` is constrained further
    by app/core/return_status.py's SHOP_ALLOWED_TRANSITIONS — a shop owner
    can only move a request forward through a defined sequence, never set
    it to an arbitrary status. `shop_note` is required by the router (not
    here) when rejecting, so the customer always sees why.
    """

    status: str
    shop_note: str | None = None

    @field_validator("shop_note")
    @classmethod
    def _note_len(cls, v: str | None) -> str | None:
        return v[:500] if v else v
