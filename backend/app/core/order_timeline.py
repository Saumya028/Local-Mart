import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrderEvent, Profile

# What a CUSTOMER may see in an event's metadata. Everything else (internal
# ids, other people's details) is for the shop/admin view only.
CUSTOMER_VISIBLE_META = ("delivery_proof_photo_url", "payment_method", "from_method", "to_method", "utr", "request_type")

_SHOP_ROLES = {"shop_owner", "manager", "delivery_partner"}


def public_actor_label(actor_role: str) -> str:
    """For the customer's view: who, without naming staff."""
    if actor_role == "customer":
        return "You"
    if actor_role in _SHOP_ROLES:
        return "The shop"
    if actor_role == "admin":
        return "LocalMart support"
    return "Automatic"


async def load_timeline(db: AsyncSession, order_id: uuid.UUID, *, for_customer: bool) -> list[dict]:
    """Oldest first. `for_customer=True` returns the safe view; otherwise
    (shop dashboard / admin) the actor's name or email and full metadata."""
    rows = (
        await db.execute(
            select(OrderEvent, Profile.full_name, Profile.email)
            .outerjoin(Profile, Profile.id == OrderEvent.actor_id)
            .where(OrderEvent.order_id == order_id)
            .order_by(OrderEvent.created_at, OrderEvent.id)
        )
    ).all()

    out = []
    for event, name, email in rows:
        if for_customer:
            actor = public_actor_label(event.actor_role)
            meta = {k: v for k, v in (event.meta or {}).items() if k in CUSTOMER_VISIBLE_META} or None
        else:
            who = name or email
            actor = f"{who} ({event.actor_role})" if who else event.actor_role
            meta = event.meta
        out.append(
            {
                "id": event.id,
                "kind": event.kind,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "actor_role": event.actor_role,
                "actor": actor,
                "note": event.note,
                "meta": meta,
                "created_at": event.created_at,
            }
        )
    return out
