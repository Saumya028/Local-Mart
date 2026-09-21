import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttributeSchema(Base):
    """
    Solves the "grocery vs pharmacy vs furniture need different product
    fields, and shops need different application fields too" problem
    without a table-per-category or a migration every time a category is
    added: one row per (kind, category) holding a field-definition list
    in `fields` (JSONB), e.g.

        [{"key": "expiry_date", "label": "Expiry Date", "type": "date",
          "required": false},
         {"key": "prescription_required", "label": "Requires prescription",
          "type": "boolean", "required": true}]

    `kind` is "product" (drives the shop-owner's Add Product form, keyed
    by the product's own `category`) or "shop" (drives the "Apply to
    sell" form, keyed by the shop's `category`) — same shape, two
    different places it's rendered.

    Field `type` is one of: text, number, select, boolean, date. `select`
    fields carry their choices in `options` (a list of strings) inside
    the field-def dict itself — there's no separate options table.

    No FK to a `categories` table because there isn't one: categories are
    free text a shop/product owner types (see Shop.category /
    Product.category), not an enum. A category with no schema row simply
    gets an empty field list — see GET /attribute-schemas/{kind}/{category}
    — so the product/shop form still works, just without extra fields,
    rather than erroring on an unrecognized category.
    """

    __tablename__ = "attribute_schemas"
    __table_args__ = (
        UniqueConstraint("kind", "category", name="uq_attribute_schemas_kind_category"),
        Index("ix_attribute_schemas_kind_category", "kind", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    fields: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
