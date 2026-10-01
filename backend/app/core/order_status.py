"""
Single source of truth for order-status semantics, shared by
routers/shop_dashboard.py and routers/admin.py so the two never quietly
drift apart (which is exactly what happened when "shipped" got renamed
to "preparing"/"ready" here but admin.py's platform_metrics still only
checked for the literal string "confirmed").

status flow: pending -> confirmed (payment succeeded, webhook-only)
                      -> payment_failed (payment failed, webhook-only)
             confirmed -> preparing -> packing -> ...

From "packing" the pipeline forks on the order's OWN
`fulfillment_type` ("delivery" or "pickup" — set once at checkout,
never changed after) — see DELIVERY_TRANSITIONS/PICKUP_TRANSITIONS
below:

  delivery: packing -> out_for_delivery -> delivered
  pickup:   packing -> ready_for_pickup -> picked_up

Both "delivered" and "picked_up" are terminal, equally-fulfilled
end states — see TERMINAL_STATUSES. Any of shop_owner/manager/
delivery_partner/admin may perform any of these transitions (see
require_role on the endpoint) — there's no per-step role restriction,
since a small shop with no staff hired yet still needs its owner alone
to move an order through every step.

There is deliberately no "cancelled"/"rejected" status anyone can set —
see the two transition maps below. Once a payment has cleared, the shop
accepts the order; there is no reject action anywhere in the product.
"""

DELIVERY_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"preparing"},
    "preparing": {"packing"},
    "packing": {"out_for_delivery"},
    "out_for_delivery": {"delivered"},
}

PICKUP_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"preparing"},
    "preparing": {"packing"},
    "packing": {"ready_for_pickup"},
    "ready_for_pickup": {"picked_up"},
}


def allowed_transitions_for(fulfillment_type: str) -> dict[str, set[str]]:
    """The map routers/shop_dashboard.py's update_order_status checks
    `payload.status` against — picked per-ORDER, never per-request, so a
    pickup order can never be walked through "out_for_delivery" and vice
    versa."""
    return PICKUP_TRANSITIONS if fulfillment_type == "pickup" else DELIVERY_TRANSITIONS


# Both fulfillment types' end states — "the order has reached the
# customer" in either sense. Order.delivered_at (see that model's
# docstring) is stamped when a status transition lands in EITHER of
# these, not just "delivered" — it's reused as a generic "fulfilled at"
# timestamp rather than adding a second, parallel `picked_up_at` column
# for what is, from the return-window's point of view
# (core/return_status.py), the exact same event.
TERMINAL_STATUSES: frozenset[str] = frozenset({"delivered", "picked_up"})

# Every status a *paid* order can be in, across BOTH fulfillment types.
# Used anywhere revenue/order counts are computed — "pending" (awaiting
# payment) and "payment_failed" never count as a sale, but an order
# doesn't stop counting just because it progressed past "confirmed"
# toward its terminal state.
RECOGNIZED_STATUSES: tuple[str, ...] = (
    "confirmed",
    "preparing",
    "packing",
    "out_for_delivery",
    "delivered",
    "ready_for_pickup",
    "picked_up",
)

# Transitioning INTO any of these statuses requires a non-empty
# `delivery_proof_photo_url` on the request — enforced in
# routers/shop_dashboard.py's update_order_status, not just at the
# frontend. Deliberately just "delivered", never "picked_up": a pickup
# is handed over in person at the counter, with the shop's own staff as
# the witness, so there's nothing a photo would additionally prove the
# way it does for a delivery person leaving an order unattended.
DELIVERY_PROOF_REQUIRED_STATUSES: frozenset[str] = frozenset({"delivered"})
