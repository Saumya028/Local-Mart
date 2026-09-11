from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set
from app.core.db import get_db
from app.models import Product, Shop
from app.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """
    We deliberately don't have a separate `categories` table — a category
    is just whatever distinct values exist in `products.category` (and,
    since the homepage's category cards show shop counts too, whatever
    distinct values exist in `shops.category`). This groups and counts
    both and merges them by name, since the two lists aren't guaranteed
    to be identical — a shop that's approved but hasn't listed any
    products yet contributes a category with shop_count > 0 and
    product_count 0, and vice versa. Worth caching either way: this
    scans two full tables and doesn't change every second.
    """

    async def load():
        product_counts = await db.execute(
            select(Product.category, func.count(Product.id))
            .where(Product.is_active.is_(True))
            .group_by(Product.category)
        )
        shop_counts = await db.execute(
            select(Shop.category, func.count(Shop.id))
            .where(Shop.is_active.is_(True), Shop.approval_status == "approved")
            .group_by(Shop.category)
        )

        products_by_category = dict(product_counts.all())
        shops_by_category = dict(shop_counts.all())
        all_names = set(products_by_category) | set(shops_by_category)

        rows = [
            {
                "name": name,
                "product_count": products_by_category.get(name, 0),
                "shop_count": shops_by_category.get(name, 0),
            }
            for name in all_names
        ]
        rows.sort(key=lambda r: r["shop_count"], reverse=True)
        return rows

    return await cache_get_or_set("categories:list", ttl_seconds=300, loader=load)
