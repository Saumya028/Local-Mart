import uuid

from app.core.redis_client import redis_client


def _cart_key(user_id: uuid.UUID) -> str:
    return f"cart:{user_id}"


async def get_cart_items(user_id: uuid.UUID) -> dict[str, int]:
    """Returns {product_id: quantity} for everything in this user's cart."""
    raw = await redis_client.hgetall(_cart_key(user_id))
    return {product_id: int(qty) for product_id, qty in raw.items()}


async def add_to_cart(user_id: uuid.UUID, product_id: str, quantity: int) -> int:
    """
    Increments the quantity for a product (creating the entry if it
    doesn't exist yet). This is what the "Add to cart" button calls —
    clicking it twice adds 2, it doesn't just set quantity to 1 twice.
    Returns the new quantity.
    """
    return await redis_client.hincrby(_cart_key(user_id), product_id, quantity)


async def set_cart_item(user_id: uuid.UUID, product_id: str, quantity: int) -> None:
    """Sets the exact quantity for a product — used by a quantity input
    on the Cart page, as opposed to the increment-only add_to_cart above.
    A quantity of 0 or less removes the item entirely."""
    key = _cart_key(user_id)
    if quantity <= 0:
        await redis_client.hdel(key, product_id)
    else:
        await redis_client.hset(key, product_id, quantity)


async def remove_from_cart(user_id: uuid.UUID, product_id: str) -> None:
    await redis_client.hdel(_cart_key(user_id), product_id)


async def clear_cart(user_id: uuid.UUID) -> None:
    """Called once checkout successfully creates orders — the cart's job
    is done at that point; the order rows are now the source of truth."""
    await redis_client.delete(_cart_key(user_id))
