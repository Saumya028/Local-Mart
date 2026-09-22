import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

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
    category: str
    stock_qty: int
    attributes: dict
    images: list
    variant_group_id: uuid.UUID | None = None
    variant_attributes: dict = {}
    is_active: bool
    created_at: datetime


class VariantSummary(BaseModel):
    """One sibling in the product's variant_group_id family, as shown on
    the swatch/variant picker on the Product Detail page — deliberately
    NOT the full ProductOut shape, just enough to render a picker and
    link to the sibling's own page (which has everything else)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    variant_attributes: dict
    price: Decimal
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


class ProductCreate(BaseModel):
    """Used by the Shop Dashboard. `shop_id` here is NEVER trusted by
    itself — the dashboard router verifies the requesting user actually
    owns that shop before this ever reaches the database."""

    shop_id: uuid.UUID
    name: str
    description: str | None = None
    price: Decimal
    category: str
    stock_qty: int = 0
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


class ProductUpdate(BaseModel):
    """All fields optional — a stock/price tweak from the dashboard
    shouldn't require resending the entire product."""

    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    category: str | None = None
    stock_qty: int | None = None
    attributes: dict | None = None
    images: list | None = None
    variant_attributes: dict | None = None
    is_active: bool | None = None
