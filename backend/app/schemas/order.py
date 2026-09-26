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
    # Added for the My Account > My Orders list (a card per order needs
    # the shop's name and a rough item count without a second round trip
    # per order) — both filled in by a join in routers/orders.py's
    # list_orders, so they default to None/0 only for callers that build
    # an OrderOut without that join (there currently are none, but the
    # defaults keep this schema safe to reuse elsewhere without a join).
    shop_name: str | None = None
    item_count: int = 0
    # Null until a shop owner marks the order "delivered" — the frontend
    # uses this (plus app/core/return_status.py's RETURN_WINDOW) to show
    # "Return by <date>" and to know when that window has closed, without
    # a second round trip just to fetch this one timestamp.
    delivered_at: datetime | None = None


class OrderItemOut(BaseModel):
    # The OrderItem row's own id — what the customer actually references
    # when opening a return/exchange (POST /orders/{id}/returns takes an
    # order_item_id, not a product_id, since the same product could in
    # theory appear more than once across an order's history).
    id: uuid.UUID
    # Guaranteed present — OrderItem.product_id is ON DELETE RESTRICT
    # against products, so a product can never actually be deleted while
    # an order references it. Used by the frontend's "Reorder" action to
    # add each item back to the cart via POST /cart/items.
    product_id: uuid.UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    # How many units of this line item are already tied up in a
    # non-cancelled/non-rejected return or exchange request — lets the
    # frontend grey out "Return" once every unit is already claimed,
    # without a separate call to list returns first.
    returned_qty: int = 0


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


class VerifyPaymentRequest(BaseModel):
    """
    What Razorpay Checkout's own `handler` callback hands back to the
    browser the instant a payment succeeds — see checkout/page.tsx.
    `razorpay_signature` is HMAC-SHA256(order_id + "|" + payment_id,
    our Razorpay key secret), so only Razorpay itself could have produced
    it; routers/orders.py's verify_payment re-derives and checks it
    server-side rather than trusting these three fields at face value.
    """

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class DashboardOrderOut(OrderOut):
    """The seller-facing view of an order — adds who bought it, which the
    customer-facing OrderOut has no reason to expose to anyone but the
    buyer themselves."""

    buyer_email: str | None
    buyer_name: str | None = None
    item_count: int = 0
