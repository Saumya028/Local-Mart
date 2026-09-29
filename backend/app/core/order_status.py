"""
Single source of truth for order-status semantics, shared by
routers/shop_dashboard.py and routers/admin.py so the two never quietly
drift apart (which is exactly what happened when "shipped" got renamed
to "preparing"/"ready" here but admin.py's platform_metrics still only
checked for the literal string "confirmed").

status flow: pending -> confirmed (payment succeeded, webhook-only)
                      -> payment_failed (payment failed, webhook-only)
             confirmed -> preparing -> packing -> out_for_delivery
                       -> delivered

This is the staff-accounts pipeline (shop owner + manager + delivery
person): "preparing" and "packing" are the kitchen/warehouse steps,
"out_for_delivery" is the delivery person actually leaving with the
order, and "delivered" is the delivery person confirming drop-off — see
DELIVERY_PROOF_REQUIRED_STATUSES below, which requires a photo for that
last step specifically. Any of shop_owner/manager/delivery/admin may
perform any of these transitions (see require_role on the endpoint) —
there's no per-step role restriction, since a small shop with no staff
hired yet still needs its owner alone to move an order through every
step.

There is deliberately no "cancelled"/"rejected" status anyone can set —
see ALLOWED_TRANSITIONS below. Once a payment has cleared, the shop
accepts the order; there is no reject action anywhere in the product.
"""

# Forward-only transitions any of shop_owner/manager/delivery/admin may
# make via PATCH /dashboard/orders/{id}/status.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"preparing"},
    "preparing": {"packing"},
    "packing": {"out_for_delivery"},
    "out_for_delivery": {"delivered"},
}

# Every status a *paid* order can be in. Used anywhere revenue/order
# counts are computed — "pending" (awaiting payment) and
# "payment_failed" never count as a sale, but an order doesn't stop
# counting just because it progressed past "confirmed" toward
# "delivered".
RECOGNIZED_STATUSES: tuple[str, ...] = (
    "confirmed",
    "preparing",
    "packing",
    "out_for_delivery",
    "delivered",
)

# Transitioning INTO any of these statuses requires a non-empty
# `delivery_proof_photo_url` on the request — enforced in
# routers/shop_dashboard.py's update_order_status, not just at the
# frontend. Currently just the final step: a delivery person (or
# whoever marks it, if a shop has no staff hired) photographs the order
# at the doorstep as proof it actually arrived.
DELIVERY_PROOF_REQUIRED_STATUSES: frozenset[str] = frozenset({"delivered"})
