import uuid

from fastapi import HTTPException


def parse_uuid_or_404(value: str, resource_name: str = "Resource") -> uuid.UUID:
    """
    Path params like /products/{product_id} arrive as plain strings —
    someone can put anything in that URL segment. Without this check, a
    malformed ID (typo, or someone poking at the API) would blow up as an
    unhandled ValueError deep inside SQLAlchemy (a 500). We'd rather fail
    the same way a "doesn't exist" ID does: a clean 404.
    """
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")
