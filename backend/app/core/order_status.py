"""
Single source of truth for order-status semantics, shared by
routers/shop_dashboard.py and routers/admin.py so the two never quietly
drift apart (which is exactly what happened when "shipped" got renamed
to "preparing"/"ready" here but admin.py's platform_metrics still only
checked for the literal string "confirmed").

status flow: pending -> confirmed (payment succeeded, webhook-only)
                      -> payment_failed (payment failed, webhook-only)
             confirmed -> preparing -> ready -> delivered (shop-owner-only)

There is deliberately no "cancelled"/"rejected" status a shop owner can
set — see ALLOWED_TRANSITIONS below. Once a payment has cleared, the
shop accepts the order; there is no reject action anywhere in the
product.
"""

# Forward-only transitions a shop owner may make via
# PATCH /dashboard/orders/{id}/status.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"preparing"},
    "preparing": {"ready"},
    "ready": {"delivered"},
}

# Every status a *paid* order can be in. Used anywhere revenue/order
# counts are computed — "pending" (awaiting payment) and
# "payment_failed" never count as a sale, but an order doesn't stop
# counting just because it progressed past "confirmed" toward
# "delivered".
RECOGNIZED_STATUSES: tuple[str, ...] = ("confirmed", "preparing", "ready", "delivered")
