"""
Validates a product's or shop's `attributes` JSON against the field
list an admin defined for its category (AttributeSchema). Shared by
both routers/shops.py (shop application/update) and
routers/shop_dashboard.py (product create/update) since the shape of
the problem — and the fix — is identical for both.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttributeSchema

ALLOWED_TYPES = {"text", "number", "select", "boolean", "date"}


async def get_schema_fields(db: AsyncSession, kind: str, category: str) -> list[dict]:
    """Returns [] for a category with no schema defined — an unrecognized
    or free-text category is never an error, just an empty field list,
    so the form/validation degrades to "no extra fields" rather than
    blocking the shop/product entirely."""
    result = await db.execute(
        select(AttributeSchema).where(AttributeSchema.kind == kind, AttributeSchema.category == category)
    )
    schema = result.scalar_one_or_none()
    return schema.fields if schema else []


async def validate_attributes(db: AsyncSession, kind: str, category: str, attributes: dict) -> None:
    """
    Raises HTTP 422 if a `required` field is missing/empty, or if a
    `select` field's value isn't one of its declared `options`. Deliberately
    does NOT reject unknown keys in `attributes` — an admin narrowing a
    schema after products already used a now-removed field shouldn't
    retroactively break every existing product; it just means that key
    stops being shown/required going forward.
    """
    fields = await get_schema_fields(db, kind, category)
    if not fields:
        return

    errors = []
    for field in fields:
        key, label = field["key"], field.get("label", field["key"])
        value = attributes.get(key)
        if field.get("required") and (value is None or value == ""):
            errors.append(f"{label} is required for category '{category}'")
        elif field.get("type") == "select" and value not in (None, ""):
            if value not in field.get("options", []):
                errors.append(f"{label} must be one of {field.get('options', [])}")

    if errors:
        raise HTTPException(status_code=422, detail={"attribute_errors": errors})
