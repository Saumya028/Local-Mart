import uuid
from datetime import datetime, timezone

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Shop(Base):
    """
    A shop is owned by exactly one profile (the seller). Every product
    belongs to a shop, never directly to a user — this is what makes the
    "platform, not seller" model concrete in the data: the platform never
    owns inventory, a shop does.
    """

    __tablename__ = "shops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    # index=True (Phase 7 hardening pass): every foreign key should have
    # one, even though nothing currently filters WHERE on it directly —
    # this is the "confirm indexes exist on every foreign key" line item,
    # not just the ones already on a hot read path.
    address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Free-text shop address + coordinates, captured on the "Apply to
    # sell" form (address_line1/city typed, lat/lng via the browser's
    # Geolocation API). Nullable because shops created before this
    # feature have none on file — GET /shops's distance filter (see
    # routers/shops.py) simply skips any shop missing coordinates rather
    # than erroring. This is deliberately separate from `addresses`,
    # which models a *customer's* delivery address, not a seller's
    # storefront location.
    address_line1: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Category-specific shop details (e.g. a pharmacy's drug license
    # number) — the field list for the current `category` comes from
    # AttributeSchema (kind="shop"), rendered dynamically on the "Apply
    # to sell" form. See ShopCreate/ShopUpdate for the same validation
    # pattern used on Product.attributes.
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # Average of the shop's visible shop reviews (see app/core/reviews.py);
    # 0 with rating_count 0 means "no reviews yet".
    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Owner-toggleable (Shop Dashboard sidebar) — whether this shop's
    # storefront/cart/checkout offer "Pick up from the shop" at all. True
    # by default so every existing shop keeps offering it unless the
    # owner turns it off; also gated at checkout time on the shop
    # actually having an address_line1 on file (see routers/orders.py's
    # checkout) — a shop with no address has nowhere for a customer to
    # go pick up from.
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Direct payments (customer pays the shop, never the platform).
    # upi_id is the shop's VPA (e.g. "shopname@okaxis"); upi_qr_url is an
    # optional uploaded QR image (public-bucket URL). Neither is exposed
    # on the public ShopOut — only shown to a customer who has actually
    # placed an order with this shop (see schemas/order.py's PayeeInfo).
    upi_id: Mapped[str | None] = mapped_column(String, nullable=True)
    upi_qr_url: Mapped[str | None] = mapped_column(String, nullable=True)
    accepts_upi: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    accepts_cash: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Admin can deactivate a shop (Phase 6) without deleting its data.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Admin Panel shop-approval workflow ("Manage Shops" > Pending
    # Approval). A brand-new shop starts "pending" and invisible on the
    # public catalog (list_shops filters on this) until an admin approves
    # it — is_active is a SEPARATE, later concern ("is this approved shop
    # currently open"), not the same flag as approval. Existing rows get
    # server_default "approved" so shops that predate this feature don't
    # vanish from the storefront.
    approval_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="approved", index=True
    )
    # Whether the seller's KYC/registration documents have been checked.
    # Independent of approval_status: an admin can request docs on an
    # already-pending application without touching its approval state.
    docs_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="verified"
    )
    # Uploaded verification documents: [{"name": "...", "doc_type": "...",
    # "url": "..."}]. Never exposed by the PUBLIC shop schema (ShopOut in
    # app/schemas/shop.py) — only the owning shop_owner (via /dashboard)
    # and admins (via /admin) can ever see these URLs. A brand-new
    # application can't be created without at least one document (see
    # ShopCreate's validator), so this starts non-empty in practice.
    documents: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # Set by an admin on reject (see routers/admin.py's reject_shop) so a
    # rejected owner knows what to fix before reapplying — cleared again
    # the next time they resubmit.
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    # Paid-priority placement: while this is in the future the shop ranks
    # above non-sponsored shops in search/listings and carries a public
    # "Sponsored" label. NULL / past = not sponsored. Admin-set only.
    sponsored_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ---- Contact & profile ---------------------------------------------
    # Public contact number shown to customers ("+91XXXXXXXXXX"). Required
    # for new applications; shops created before this existed have NULL.
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- Opening hours -------------------------------------------------
    # {"mon": [{"open": "09:00", "close": "21:00"}], ..., "sun": []}
    # A day mapped to [] is closed all day. NULL = the owner hasn't set any
    # hours yet, which means "always open" so shops that existed before this
    # feature keep working. See app/core/shop_hours.py for the rules
    # (overnight ranges, "24:00", ...).
    opening_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timezone: Mapped[str] = mapped_column(String, default="Asia/Kolkata", server_default="Asia/Kolkata")
    # Vacation / "closed for now" switch. Visible to customers (unlike
    # is_active, which unlists the shop entirely). `closed_until` reopens it
    # automatically; NULL means "until the owner switches it back".
    temporarily_closed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    closed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # ---- Delivery pricing (applies to DELIVERY orders only) --------------
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")
    # Order subtotal at/above which delivery is free. NULL = never free.
    free_delivery_above: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Minimum item subtotal for a delivery order. 0 = no minimum.
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, server_default="0")

    # ---- GST / invoicing ----------------------------------------------
    # The shop's own GSTIN (unset = unregistered: invoices say "Invoice",
    # not "Tax Invoice") and the legal name to print on them.
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Last invoice number handed out (incremented atomically).
    invoice_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # ---- Inventory ------------------------------------------------------
    # Owners are alerted when a product's stock falls to this many (a product
    # can override it with its own `low_stock_threshold`).
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=5, server_default="5")

    # ---- Timing: ETA and optional scheduled slots -----------------------
    prep_time_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    delivery_time_minutes: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    slots_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    slot_length_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    # Max non-cancelled orders per slot.
    slot_capacity: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    # How many calendar days (today included) customers can book into.
    slot_days_ahead: Mapped[int] = mapped_column(Integer, default=2, server_default="2")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def open_info(self) -> dict:
        """Computed (never stored): is the shop taking orders right now,
        and when does that change? Read by ShopOut so every public shop
        response carries it."""
        from app.core.shop_hours import open_status

        return open_status(self).as_dict()

    @property
    def is_sponsored(self) -> bool:
        return self.sponsored_until is not None and self.sponsored_until > datetime.now(timezone.utc)

    # Composite index (Phase 7): GET /shops's hottest query is exactly
    # `WHERE is_active = true ORDER BY rating DESC LIMIT 50` — this one
    # index serves both the filter and the sort together, rather than
    # Postgres using a single-column index for one and sorting the rest
    # in memory.
    __table_args__ = (
        Index("ix_shops_is_active_rating", "is_active", "rating"),
        Index("ix_shops_lat_lng", "latitude", "longitude"),
    )
