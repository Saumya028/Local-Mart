import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    rating: float
    is_active: bool
    created_at: datetime
