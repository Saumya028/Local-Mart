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
    is_active: bool
    created_at: datetime


class ProductDetailOut(ProductOut):
    """Shape returned by the single-product endpoint — the Product Detail
    page needs to show who's selling it, so this adds the nested shop."""

    shop: ShopOut | None = None


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
    is_active: bool | None = None
