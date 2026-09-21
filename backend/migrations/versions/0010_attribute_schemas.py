"""Category-driven product/shop attribute schemas

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-21

The product-add form collected the same 4 fields (name/category/price/
stock) no matter what was being sold, and the shop application form had
no way to ask a grocery shop for an FSSAI number or a pharmacy for a
drug license number. `attribute_schemas` is what fixes that without a
table-per-category: one row per (kind, category) holding a JSON list of
field definitions, which the frontend uses to render extra fields
dynamically (see routers/attribute_schemas.py's docstring, and the
AttributeSchema model for the field-def shape).

products.attributes (JSONB) already existed unused — this is what
finally puts it to work. shops had no equivalent column at all until
this migration.

Seeds a starting set of schemas for the categories this app already
uses (see lib/categoryVisuals.ts) so the feature is demonstrable
immediately rather than shipping empty — an admin can add more or edit
these via the new /admin/attribute-schemas endpoints and the Admin
Panel's "Attributes" tab.
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

PRODUCT_SCHEMAS = {
    "Groceries": [
        {"key": "unit", "label": "Unit", "type": "select", "required": True,
         "options": ["kg", "g", "litre", "ml", "piece", "packet"]},
        {"key": "weight", "label": "Weight / Volume per unit", "type": "text", "required": False},
        {"key": "brand", "label": "Brand", "type": "text", "required": False},
        {"key": "expiry_date", "label": "Expiry date", "type": "date", "required": False},
    ],
    "Bakery": [
        {"key": "unit", "label": "Unit", "type": "select", "required": True,
         "options": ["piece", "box", "kg", "dozen"]},
        {"key": "contains_egg", "label": "Contains egg", "type": "boolean", "required": False},
        {"key": "shelf_life", "label": "Shelf life", "type": "text", "required": False},
    ],
    "Pharmacy": [
        {"key": "composition", "label": "Composition / Salt", "type": "text", "required": False},
        {"key": "dosage_form", "label": "Dosage form", "type": "select", "required": False,
         "options": ["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Other"]},
        {"key": "prescription_required", "label": "Requires prescription", "type": "boolean", "required": True},
        {"key": "manufacturer", "label": "Manufacturer", "type": "text", "required": False},
    ],
    "Electronics": [
        {"key": "brand", "label": "Brand", "type": "text", "required": True},
        {"key": "model", "label": "Model number", "type": "text", "required": False},
        {"key": "warranty_months", "label": "Warranty (months)", "type": "number", "required": False},
    ],
    "Fashion": [
        {"key": "size", "label": "Size", "type": "select", "required": True,
         "options": ["XS", "S", "M", "L", "XL", "XXL", "Free Size"]},
        {"key": "color", "label": "Color", "type": "text", "required": False},
        {"key": "material", "label": "Material", "type": "text", "required": False},
    ],
    "Stationery": [
        {"key": "brand", "label": "Brand", "type": "text", "required": False},
        {"key": "pack_size", "label": "Pack size", "type": "text", "required": False},
    ],
    "Home & Living": [
        {"key": "material", "label": "Material", "type": "text", "required": False},
        {"key": "dimensions", "label": "Dimensions (L x W x H)", "type": "text", "required": False},
        {"key": "assembly_required", "label": "Assembly required", "type": "boolean", "required": False},
        {"key": "warranty_months", "label": "Warranty (months)", "type": "number", "required": False},
    ],
    "Restaurants": [
        {"key": "spice_level", "label": "Spice level", "type": "select", "required": False,
         "options": ["Mild", "Medium", "Spicy"]},
        {"key": "is_veg", "label": "Vegetarian", "type": "boolean", "required": True},
        {"key": "serves", "label": "Serves (approx. people)", "type": "number", "required": False},
    ],
}

SHOP_SCHEMAS = {
    "Groceries": [
        {"key": "fssai_number", "label": "FSSAI License Number", "type": "text", "required": False},
    ],
    "Bakery": [
        {"key": "fssai_number", "label": "FSSAI License Number", "type": "text", "required": False},
    ],
    "Pharmacy": [
        {"key": "drug_license_number", "label": "Drug License Number", "type": "text", "required": True},
        {"key": "pharmacist_registration_number", "label": "Pharmacist Registration Number",
         "type": "text", "required": True},
    ],
    "Restaurants": [
        {"key": "fssai_number", "label": "FSSAI License Number", "type": "text", "required": True},
    ],
}

attribute_schemas_table = sa.table(
    "attribute_schemas",
    sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("kind", sa.String),
    sa.column("category", sa.String),
    sa.column("fields", JSONB),
)


def upgrade() -> None:
    op.create_table(
        "attribute_schemas",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("fields", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("kind", "category", name="uq_attribute_schemas_kind_category"),
    )
    op.create_index("ix_attribute_schemas_kind_category", "attribute_schemas", ["kind", "category"])

    op.add_column("shops", sa.Column("attributes", JSONB, nullable=False, server_default="{}"))

    rows = [
        {"id": uuid.uuid4(), "kind": "product", "category": cat, "fields": fields}
        for cat, fields in PRODUCT_SCHEMAS.items()
    ] + [
        {"id": uuid.uuid4(), "kind": "shop", "category": cat, "fields": fields}
        for cat, fields in SHOP_SCHEMAS.items()
    ]
    op.bulk_insert(attribute_schemas_table, rows)


def downgrade() -> None:
    op.drop_column("shops", "attributes")
    op.drop_index("ix_attribute_schemas_kind_category", table_name="attribute_schemas")
    op.drop_table("attribute_schemas")
