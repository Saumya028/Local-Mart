"""
Low-stock alerts for shop owners.

A product is in one of three alert states, stored on `products.low_stock_state`:
    None   stock is above the alert level
    "low"  0 < stock <= threshold
    "out"  stock <= 0
The threshold is the product's own `low_stock_threshold`, else the shop's
default (`shops.low_stock_threshold`, 5 unless changed).

Alerts are EDGE-triggered: the owner and managers are notified (bell + email,
through the normal notification system) when a product ENTERS "low" or "out",
not on every sale while it stays low. Restocking above the level silently
re-arms it.

Race-safety: the new state is written with a compare-and-set
(`UPDATE ... WHERE low_stock_state IS DISTINCT FROM :new RETURNING id`), so if
two checkouts push a product under the line at once, exactly one of them
"wins" the transition and sends the alert.

Call `sync_stock_alerts` after any change to stock, threshold or active
status, in the SAME transaction (before commit). It never raises: a problem
here must not stop an order or a stock edit.
"""
import logging
from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_templates import Msg
from app.core.notifications import create_notification, shop_team
from app.models import Product, Shop

logger = logging.getLogger(__name__)


def effective_threshold(product: Product, shop_default: int) -> int:
    return product.low_stock_threshold if product.low_stock_threshold is not None else shop_default


def stock_state(stock_qty: int, threshold: int) -> str | None:
    if stock_qty <= 0:
        return "out"
    if threshold > 0 and stock_qty <= threshold:
        return "low"
    return None


def _message(product: Product, state: str, threshold: int) -> Msg:
    if state == "out":
        return Msg(
            f"Out of stock: {product.name}",
            f"{product.name} just sold out. Customers can’t order it until you restock.",
        )
    return Msg(
        f"Low stock: {product.name}",
        f"Only {product.stock_qty} left (your alert level is {threshold}). Restock soon to keep selling.",
    )


async def sync_stock_alerts(db: AsyncSession, product_ids: Iterable, *, notify: bool = True) -> None:
    """Bring each product's alert state in line with its current stock.
    `notify=False` updates the state without sending anything (use it for
    changes the owner made themselves, or restocks)."""
    ids = list(dict.fromkeys(product_ids))
    if not ids:
        return
    try:
        async with db.begin_nested():
            # populate_existing: stock was just changed with a Core UPDATE, so any
            # Product object already in this session is stale.
            rows = (
                await db.execute(
                    select(Product, Shop)
                    .join(Shop, Shop.id == Product.shop_id)
                    .where(Product.id.in_(ids))
                    .execution_options(populate_existing=True)
                )
            ).all()
            for product, shop in rows:
                threshold = effective_threshold(product, shop.low_stock_threshold)
                new_state = stock_state(product.stock_qty, threshold) if product.is_active else None
                flipped = (
                    await db.execute(
                        update(Product)
                        .where(Product.id == product.id, Product.low_stock_state.is_distinct_from(new_state))
                        .values(low_stock_state=new_state)
                        .returning(Product.id)
                        .execution_options(synchronize_session=False)
                    )
                ).first()
                if flipped is None or new_state is None or not notify:
                    continue
                # Only a real worsening is worth an alert (None->low, None->out, low->out).
                # (Entering "low" from "out" after a partial restock isn't.)
                if product.low_stock_state == "out" and new_state == "low":
                    continue
                msg = _message(product, new_state, threshold)
                for member in await shop_team(db, shop):
                    await create_notification(
                        db, member, msg,
                        kind="out_of_stock" if new_state == "out" else "low_stock",
                        link="/shop/dashboard?tab=inventory",
                        data={"product_id": str(product.id), "shop_id": str(shop.id)},
                    )
    except Exception:
        logger.exception("stock alert sync failed — the stock change itself is unaffected")


async def sync_shop_stock_alerts(db: AsyncSession, shop_id, *, notify: bool = False) -> None:
    """Re-evaluate every product of a shop (after its default threshold changed)."""
    ids = (await db.execute(select(Product.id).where(Product.shop_id == shop_id))).scalars().all()
    await sync_stock_alerts(db, ids, notify=notify)
