import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.product_pricing import UNITS, clean_barcode, clean_sku
from app.schemas.shop import ShopOut


class ProductOut(BaseModel):
    """Shape returned by list/search/dashboard endpoints — no shop details
    embedded, since a grid or a seller's own product list doesn't need
    them and it keeps the payload smaller for the endpoints returning the
    most rows at once."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shop_id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    # Maximum Retail Price (optional). `price` is what the customer pays.
    mrp: Decimal | None = None
    unit_value: Decimal | None = None
    unit: str | None = None
    # Computed: "500 g", "15" (percent off MRP), "₹8 / 100 g".
    unit_label: str | None = None
    discount_percent: int | None = None
    unit_price_label: str | None = None
    category: str
    stock_qty: int
    attributes: dict
    images: list
    variant_group_id: uuid.UUID | None = None
    variant_attributes: dict = {}
    is_active: bool
    created_at: datetime
    # Stored aggregates over visible reviews — see app/core/reviews.py.
    rating_avg: float = 0.0
    rating_count: int = 0


class ProductDashboardOut(ProductOut):
    """What a shop owner/manager sees: the public fields plus their own
    stock code, barcode and low-stock settings."""

    sku: str | None = None
    barcode: str | None = None
    low_stock_threshold: int | None = None
    # The threshold actually in force (the product's own, else the shop's).
    effective_low_stock_threshold: int = 5
    # "ok" | "low" | "out" — from the CURRENT stock.
    stock_status: str = "ok"


class ProductSearchOut(ProductOut):
    """Search-result row: a product plus its shop's name (and distance
    when the search included a location). Sponsorship only affects the
    ORDER of rows; it is deliberately not exposed in the response."""

    shop_name: str | None = None
    # Only set when the search included lat/lng.
    distance_km: float | None = None


class VariantSummary(BaseModel):
    """One sibling in the product's variant_group_id family, as shown on
    the swatch/variant picker on the Product Detail page — deliberately
    NOT the full ProductOut shape, just enough to render a picker and
    link to the sibling's own page (which has everything else)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_attributes: dict
    price: Decimal
    mrp: Decimal | None = None
    unit_label: str | None = None
    discount_percent: int | None = None
    stock_qty: int
    is_active: bool
    thumbnail: str | None = None


class ProductDetailOut(ProductOut):
    """Shape returned by the single-product endpoint — the Product Detail
    page needs to show who's selling it, so this adds the nested shop."""

    shop: ShopOut | None = None
    # [] when variant_group_id is None, or when it's the only active
    # product left in its group — the picker only renders when there's
    # actually something to pick between (see routers/products.py).
    variants: list[VariantSummary] = []
    # attribute key -> display label, so the page needs no extra request.
    attribute_labels: dict[str, str] = {}


def _check_unit(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().lower()
    if not v:
        return None
    if v not in UNITS:
        raise ValueError(f"Unit must be one of: {', '.join(UNITS)}")
    return v


class ProductCreate(BaseModel):
    """Used by the Shop Dashboard. `shop_id` here is NEVER trusted by
    itself — the dashboard router verifies the requesting user actually
    owns that shop before this ever reaches the database."""

    shop_id: uuid.UUID
    name: str
    description: str | None = None
    price: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)
    category: str
    stock_qty: int = Field(default=0, ge=0, le=1_000_000)
    attributes: dict = {}
    images: list = []
    # Pick an EXISTING product (must belong to the same shop) to make
    # this a variant of — see routers/shop_dashboard.py's create_product
    # for how this resolves to a shared variant_group_id, promoting the
    # sibling into a group if it wasn't already in one. Omit for a
    # standalone product (the default, same as before variants existed).
    variant_of_product_id: uuid.UUID | None = None
    # What's different about THIS row vs its siblings, e.g. {"Color":
    # "Black"} — ignored (stored as {}) when variant_of_product_id is
    # None, since a standalone product has nothing to differ from.
    variant_attributes: dict = {}
    # ---- pricing, size & identifiers ---------------------------------------
    mrp: Decimal | None = Field(default=None, gt=0, le=10_000_000, decimal_places=2)
    unit_value: Decimal | None = Field(default=None, gt=0, le=100_000, decimal_places=3)
    unit: str | None = None
    sku: str | None = None
    barcode: str | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("unit")
    @classmethod
    def _unit(cls, v):
        return _check_unit(v)

    @field_validator("sku")
    @classmethod
    def _sku(cls, v):
        return clean_sku(v)

    @field_validator("barcode")
    @classmethod
    def _barcode(cls, v):
        return clean_barcode(v)

    @model_validator(mode="after")
    def _consistent(self):
        if self.mrp is not None and self.mrp < self.price:
            raise ValueError("MRP can't be lower than the selling price")
        if (self.unit_value is None) != (self.unit is None):
            raise ValueError("Give both the pack size and its unit (e.g. 500 and g), or neither")
        return self


class ProductUpdate(BaseModel):
    """All fields optional — a stock/price tweak from the dashboard
    shouldn't require resending the entire product."""

    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, le=10_000_000, decimal_places=2)
    category: str | None = None
    stock_qty: int | None = Field(default=None, ge=0, le=1_000_000)
    attributes: dict | None = None
    images: list | None = None
    variant_attributes: dict | None = None
    is_active: bool | None = None
    # ---- pricing, size & identifiers (cross-field rules are checked in the
    # router against the product's CURRENT values, since this is a partial update)
    mrp: Decimal | None = Field(default=None, gt=0, le=10_000_000, decimal_places=2)
    unit_value: Decimal | None = Field(default=None, gt=0, le=100_000, decimal_places=3)
    unit: str | None = None
    sku: str | None = None
    barcode: str | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("unit")
    @classmethod
    def _unit(cls, v):
        return _check_unit(v)

    @field_validator("sku")
    @classmethod
    def _sku(cls, v):
        return clean_sku(v)

    @field_validator("barcode")
    @classmethod
    def _barcode(cls, v):
        return clean_barcode(v)
