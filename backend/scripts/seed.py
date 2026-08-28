"""
Populates the database with a handful of demo shops and products.

Why this exists: the Shop Dashboard (where real shop owners will create
their own listings) doesn't exist until Phase 5. Without it, the tables
this phase reads from are empty and there's nothing to see on the pages
we just built. This script creates one demo "shop owner" profile directly
(bypassing signup — it's not a real login-able account, just a row to
satisfy the foreign key) and a few shops/products under it.

Run once, from the backend/ directory, with your virtualenv active and
.env configured:

    python -m scripts.seed

Safe to re-run — it will create duplicate rows if run twice, since this
is throwaway dev data. Truncate the tables in Supabase's Table Editor
first if you want a clean slate before re-seeding.
"""
import asyncio
import uuid

from app.core.db import AsyncSessionLocal
from app.models import Product, Profile, Shop

DEMO_OWNER_ID = uuid.uuid4()

SHOPS = [
    {"name": "Fresh Valley Groceries", "category": "Groceries"},
    {"name": "Corner Bakery", "category": "Bakery"},
    {"name": "QuickCare Pharmacy", "category": "Pharmacy"},
    {"name": "TechHub Electronics", "category": "Electronics"},
]

PRODUCTS_BY_CATEGORY = {
    "Groceries": [
        {"name": "Organic Bananas (1kg)", "price": 60, "stock_qty": 100, "attributes": {"weight_kg": 1}},
        {"name": "Basmati Rice (5kg)", "price": 450, "stock_qty": 40, "attributes": {"weight_kg": 5}},
    ],
    "Bakery": [
        {"name": "Sourdough Loaf", "price": 120, "stock_qty": 20, "attributes": {}},
        {"name": "Chocolate Croissant", "price": 80, "stock_qty": 30, "attributes": {}},
    ],
    "Pharmacy": [
        {"name": "Vitamin C Tablets (60ct)", "price": 250, "stock_qty": 50, "attributes": {"count": 60}},
    ],
    "Electronics": [
        {"name": "USB-C Cable (1m)", "price": 299, "stock_qty": 75, "attributes": {"length_m": 1}},
        {"name": "Wireless Mouse", "price": 899, "stock_qty": 25, "attributes": {"color": "black"}},
    ],
}


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        owner = Profile(id=DEMO_OWNER_ID, email="demo-owner@localmart.dev", role="shop_owner")
        db.add(owner)
        await db.flush()  # so owner.id is usable as a foreign key below, before commit

        for shop_data in SHOPS:
            shop = Shop(id=uuid.uuid4(), owner_id=owner.id, **shop_data)
            db.add(shop)
            await db.flush()

            for product_data in PRODUCTS_BY_CATEGORY[shop_data["category"]]:
                db.add(
                    Product(
                        id=uuid.uuid4(),
                        shop_id=shop.id,
                        category=shop_data["category"],
                        description=f"Demo product for {shop_data['name']}",
                        images=[],
                        **product_data,
                    )
                )

        await db.commit()

    print("Seed complete: 4 shops, 7 products created.")


if __name__ == "__main__":
    asyncio.run(seed())
