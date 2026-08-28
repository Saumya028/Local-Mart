import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.shop import ShopOut


class ProductOut(BaseModel):
    """Shape returned by list/search endpoints — no shop details embedded,
    since a search results grid doesn't need them and it keeps the payload
    smaller for the endpoint that returns the most rows at once."""

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
