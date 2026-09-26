"""
Single source of truth for return/exchange status semantics — mirrors
the role app/core/order_status.py plays for order statuses, shared by
routers/returns.py (customer side) and routers/shop_dashboard.py (shop
side) so the two never quietly drift apart on what's legal from where.

status flow: requested -> approved -> completed  (shop accepts, then
                                                    confirms the pickup/
                                                    refund or exchange is
                                                    actually done)
             requested -> rejected                (shop declines, with a
                                                    shop_note explaining
                                                    why)
             requested -> cancelled                (customer backs out,
                                                    only before the shop
                                                    has acted)
"""

from datetime import timedelta

# How long after DELIVERY a customer may open a return/exchange request.
# Amazon/Flipkart-style marketplaces use a fixed window like this rather
# than an unlimited one — a single named constant here, rather than a
# magic number scattered across routers/returns.py, is what keeps this
# easy to change (or make per-category/per-shop) later without hunting.
RETURN_WINDOW = timedelta(days=7)

REQUEST_TYPES: tuple[str, ...] = ("return", "exchange")

# Every order status a return/exchange may be opened against. Deliberately
# just "delivered" — a pending/confirmed/preparing/ready order hasn't
# reached the customer yet, so there's nothing to return.
RETURN_ELIGIBLE_ORDER_STATUSES: set[str] = {"delivered"}

# Forward-only transitions a SHOP OWNER may make via
# PATCH /dashboard/returns/{id}/status.
SHOP_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "requested": {"approved", "rejected"},
    "approved": {"completed"},
}

# The only transition a CUSTOMER may make themselves, via
# POST /returns/{id}/cancel — and only while the shop hasn't acted on it
# yet. Once a shop has approved or rejected a request, the customer can
# no longer unilaterally cancel it (approved: the shop is already
# expecting a pickup; rejected: there's nothing left to cancel).
CUSTOMER_CANCELABLE_FROM: set[str] = {"requested"}

TERMINAL_STATUSES: set[str] = {"completed", "rejected", "cancelled"}
