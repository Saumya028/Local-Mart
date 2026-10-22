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


LIKE_ESCAPE_CHAR = "\\"


def escape_like(value: str) -> str:
    """
    Escapes `%`, `_` and the escape character itself so user input is
    matched literally inside an ILIKE pattern. Without this, searching for
    "50%" or "_" turns the user's text into wildcards (matching everything).
    Use as: `col.ilike(f"%{escape_like(q)}%", escape=LIKE_ESCAPE_CHAR)`.
    """
    return (
        value.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", LIKE_ESCAPE_CHAR + "%")
        .replace("_", LIKE_ESCAPE_CHAR + "_")
    )
