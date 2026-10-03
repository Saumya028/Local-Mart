import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.shop import ShopOut


class CheckoutRequest(BaseModel):
    # Optional now that pickup exists: only required if at least one shop
    # in the cart is NOT in pickup_shop_ids below (see routers/orders.py's
    # checkout, which raises its own clear 400 if it's missing but
    # needed). Still resolved into a formatted text snapshot stored on
    # each delivery Order, so the order still shows the correct address
    # even if the address book entry is later edited or deleted.
    address_id: uuid.UUID | None = None
    # Cart items are already grouped by shop into separate Order rows
    # (see the Order model's docstring) — this lets a customer pick up
    # from SOME shops in their cart while having others delivered, in
    # one checkout. Any shop_id here gets fulfillment_type="pickup"
    # (rejected with a 400 if that shop doesn't offer pickup); every
    # other shop in the cart gets "delivery" to address_id.
    pickup_shop_ids: list[uuid.UUID] = []
    # shop_id -> "upi" | "cash", one entry per shop in the cart. Payment
    # goes straight from the customer to each shop, so it's chosen per
    # shop (= per order). Validated in routers/orders.py against what
    # each shop actually accepts.
    payment_methods: dict[uuid.UUID, str] = {}


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shop_id: uuid.UUID
    status: str
    # "delivery" or "pickup" — see Order.fulfillment_type. Decides how
    # the frontend labels status/timeline text and whether
    # delivery_address or the shop's own address is what's shown.
    fulfillment_type: str = "delivery"
    total_amount: Decimal
    delivery_address: str | None = None
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
    # Set once a delivery person (or whoever marks it, if the shop has
    # no staff hired) confirms drop-off — see app/core/order_status.py's
    # DELIVERY_PROOF_REQUIRED_STATUSES. Shown on the customer's own
    # order-tracking page as proof of delivery, not just in the shop's
    # dashboard.
    delivery_proof_photo_url: str | None = None
    # Direct-payment state, filled in by a join on payments — see
    # app/models/payment.py. None only for very old orders with no
    # Payment row.
    payment_method: str | None = None
    payment_status: str | None = None


class PaymentInfo(BaseModel):
    """Everything the customer's order page needs to pay the shop
    directly. The shop's UPI id / QR are only ever returned here, to the
    customer who owns the order — never on the public shop endpoints."""

    method: str
    status: str
    amount: Decimal
    payer_reference: str | None = None
    payee_name: str | None = None
    upi_id: str | None = None
    upi_qr_url: str | None = None
    # Ready-made upi://pay deep link (only for method="upi").
    upi_link: str | None = None
    # What the shop currently accepts, so the page can offer a switch.
    shop_accepts_upi: bool = False
    shop_accepts_cash: bool = False


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
    payment: PaymentInfo | None = None


class OrderStatusUpdate(BaseModel):
    # Constrained further in routers/shop_dashboard.py's
    # update_order_status, against whichever of
    # app/core/order_status.py's two transition maps matches this
    # order's OWN fulfillment_type — shop staff can only move an order
    # forward through that one defined sequence, never set it to an
    # arbitrary status or the other fulfillment type's steps.
    status: str
    # Required (validated server-side, not just here) when `status` is
    # "delivered" — see app/core/order_status.py's
    # DELIVERY_PROOF_REQUIRED_STATUSES. A public-bucket URL the frontend
    # uploads to first (same pattern as product images), not a raw file.
    delivery_proof_photo_url: str | None = None


class CheckoutResponse(BaseModel):
    orders: list[OrderOut]
    total_amount: Decimal


class MarkPaidRequest(BaseModel):
    """Customer: "I've paid by UPI". The UTR is optional but helps the
    shop find the transfer in their bank/UPI app."""

    payer_reference: str | None = None


class ChangePaymentMethodRequest(BaseModel):
    method: str


class DashboardOrderOut(OrderOut):
    """The seller-facing view of an order — adds who bought it, which the
    customer-facing OrderOut has no reason to expose to anyone but the
    buyer themselves."""

    buyer_email: str | None
    buyer_name: str | None = None
    item_count: int = 0
    payer_reference: str | None = None
    payment_marked_at: datetime | None = None
