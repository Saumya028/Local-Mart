import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProfileOut(BaseModel):
    """
    What we send back to the frontend for a profile. Separate from the
    SQLAlchemy model on purpose — the API's shape shouldn't be forced to
    match the database's shape 1:1 forever (e.g. we'd never want to
    accidentally expose an internal-only column just because it exists
    on the model).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime
