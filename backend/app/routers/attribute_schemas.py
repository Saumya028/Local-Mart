from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attribute_validation import get_schema_fields
from app.core.cache import cache_get_or_set
from app.core.db import get_db

router = APIRouter(prefix="/attribute-schemas", tags=["attribute-schemas"])


@router.get("/{kind}/{category}")
async def get_attribute_schema(kind: str, category: str, db: AsyncSession = Depends(get_db)):
    """
    Public and unauthenticated on purpose — this drives two different
    forms that both need it before the person filling them in has
    necessarily signed in: the "Apply to sell" form (kind="shop") and
    the Shop Dashboard's Add/Edit Product form (kind="product", which
    IS behind auth, but there's no reason to duplicate this endpoint
    just for that).

    Always 200, never 404 — a category with nothing defined for it just
    returns an empty `fields` list (see get_schema_fields's docstring),
    so the calling form renders its fixed fields and simply skips the
    dynamic section rather than having to special-case "no schema yet".
    """
    cache_key = f"attribute-schema:{kind}:{category}"

    async def load():
        return {"kind": kind, "category": category, "fields": await get_schema_fields(db, kind, category)}

    return await cache_get_or_set(cache_key, ttl_seconds=300, loader=load)
