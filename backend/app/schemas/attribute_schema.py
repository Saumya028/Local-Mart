import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_TYPES = {"text", "number", "select", "boolean", "date"}


class AttributeField(BaseModel):
    """One field in a category's dynamic form. `options` only means
    anything when type == "select"; left as [] otherwise."""

    key: str
    label: str
    type: str
    required: bool = False
    options: list[str] = []

    @field_validator("type")
    @classmethod
    def type_is_known(cls, v: str) -> str:
        if v not in ALLOWED_TYPES:
            raise ValueError(f"type must be one of {sorted(ALLOWED_TYPES)}")
        return v

    @field_validator("key")
    @classmethod
    def key_is_safe(cls, v: str) -> str:
        # Keys become JSONB object keys and, on the frontend, form field
        # names — keep them to what a `attributes[key]` lookup and a
        # stable React key both expect, nothing that could collide with
        # a reserved word or get mangled in a URL/JSON round-trip.
        if not v or not v.replace("_", "").isalnum():
            raise ValueError("key must be alphanumeric/underscore only, e.g. 'expiry_date'")
        return v


class AttributeSchemaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    category: str
    fields: list[AttributeField]
    updated_at: datetime


class AttributeSchemaUpsert(BaseModel):
    """Admin-only — PUT /admin/attribute-schemas/{kind}/{category}
    replaces the whole field list (not a partial patch): a category's
    form is one coherent set of fields, not something you'd usually
    tweak one field at a time from two different requests."""

    fields: list[AttributeField]
