import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.product import ProductOut


class WishlistAddRequest(BaseModel):
    product_id: uuid.UUID


class WishlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product: ProductOut
    shop_name: str | None = None
    added_at: datetime
