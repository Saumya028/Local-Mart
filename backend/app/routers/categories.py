from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set
from app.core.db import get_db
from app.models import Product
from app.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """
    We deliberately don't have a separate `categories` table — a category
    is just whatever distinct values exist in `products.category`. This
    query groups and counts them. It's the kind of aggregate query worth
    caching, since it scans the whole products table and doesn't change
    every second — a 5 minute TTL is fine for a category list.
    """

    async def load():
        stmt = (
            select(Product.category, func.count(Product.id))
            .where(Product.is_active.is_(True))
            .group_by(Product.category)
            .order_by(func.count(Product.id).desc())
        )
        result = await db.execute(stmt)
        return [{"name": name, "product_count": count} for name, count in result.all()]

    return await cache_get_or_set("categories:list", ttl_seconds=300, loader=load)
