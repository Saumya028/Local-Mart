import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.shop import ShopOut


class CheckoutRequest(BaseModel):
    # Replaces the free-text delivery_address field from Phase 3 — the
    # customer now selects a saved address instead of retyping one every
    # checkout. The backend resolves this into a formatted text snapshot
    # stored on the Order (see routers/orders.py), so the order still
    # shows the correct address even if the address book entry is later
    # edited or deleted.
    address_id: uuid.UUID


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shop_id: uuid.UUID
    status: str
    total_amount: Decimal
    delivery_address: str
    created_at: datetime


class OrderItemOut(BaseModel):
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderDetailOut(OrderOut):
    """Extra detail for the single-order view (tracking page) — the list
    endpoint returns plain OrderOut, since a history list doesn't need
    every line item, just enough to identify and link to each order."""

    shop: ShopOut | None = None
    items: list[OrderItemOut] = []


class OrderStatusUpdate(BaseModel):
    # Constrained further in routers/shop_dashboard.py's ALLOWED_TRANSITIONS
    # map — a shop owner can only move an order forward through a defined
    # sequence (confirmed -> shipped -> delivered), never set it to an
    # arbitrary status.
    status: str


class CheckoutResponse(BaseModel):
    orders: list[OrderOut]
    # Handed to the frontend's Razorpay Checkout widget, along with
    # razorpay_key_id, to open the payment popup for this specific order.
    razorpay_order_id: str
    razorpay_key_id: str
    total_amount: Decimal


class DashboardOrderOut(OrderOut):
    """The seller-facing view of an order — adds who bought it, which the
    customer-facing OrderOut has no reason to expose to anyone but the
    buyer themselves."""

    buyer_email: str


class OrderStatusUpdate(BaseModel):
    status: str
