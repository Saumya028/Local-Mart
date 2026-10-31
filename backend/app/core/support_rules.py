"""
Single source of truth for customer-support rules, shared by the customer,
shop and admin routers (same idea as core/order_status.py and
core/return_status.py). Pure functions, no database — easy to unit-test.
"""
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.order_status import TERMINAL_STATUSES

# --- what can be reported ---------------------------------------------------
KINDS: tuple[str, ...] = ("order_problem", "payment_problem", "shop_report", "general")
ORDER_KINDS: frozenset[str] = frozenset({"order_problem", "payment_problem"})
# Go straight to admin: no shop reply step.
ADMIN_DIRECT_KINDS: frozenset[str] = frozenset({"shop_report", "general"})

# kind -> {reason code: label shown to people}. Fixed lists so admin can filter
# and spot patterns.
REASONS: dict[str, dict[str, str]] = {
    "order_problem": {
        "not_delivered": "Order not delivered",
        "wrong_item": "Wrong item received",
        "missing_items": "Items missing from my order",
        "damaged_item": "Item damaged or spoiled",
        "quality_issue": "Quality isn't as described",
        "wrong_amount": "Charged the wrong amount",
        "other": "Something else",
    },
    "payment_problem": {
        "paid_not_confirmed": "I paid but the shop says it wasn't received",
        "charged_twice": "I was charged twice",
        "refund_not_received": "I haven't received my refund",
        "other": "Something else",
    },
    "shop_report": {
        "fake_shop": "This shop looks fake",
        "misleading_listing": "Misleading products or prices",
        "abusive_behaviour": "Rude or abusive behaviour",
        "unsafe_products": "Unsafe or expired products",
        "other": "Something else",
    },
    "general": {
        "app_bug": "Something in the app isn't working",
        "account_issue": "Problem with my account",
        "other": "Something else",
    },
}

KIND_LABELS = {
    "order_problem": "Order problem",
    "payment_problem": "Payment problem",
    "shop_report": "Shop report",
    "general": "General issue",
}

# --- statuses ---------------------------------------------------------------
OPEN = "open"                    # waiting for the shop
NEEDS_INFO = "needs_info"        # shop asked the customer something (once)
SHOP_REPLIED = "shop_replied"    # waiting for the customer: accept or escalate
ESCALATED = "escalated"          # with admin
ACTION_PENDING = "action_pending"  # admin ruled; shop must refund/resend
RESOLVED = "resolved"

STATUSES: tuple[str, ...] = (OPEN, NEEDS_INFO, SHOP_REPLIED, ESCALATED, ACTION_PENDING, RESOLVED)
# Statuses in which the customer can still accept/close or escalate.
CUSTOMER_ACTIVE: frozenset[str] = frozenset({OPEN, NEEDS_INFO, SHOP_REPLIED})
# Statuses in which the shop may still send its single reply.
SHOP_CAN_REPLY: frozenset[str] = frozenset({OPEN})
# Admin may rule on anything that isn't finished or already waiting on the shop.
ADMIN_CAN_RULE: frozenset[str] = frozenset({OPEN, NEEDS_INFO, SHOP_REPLIED, ESCALATED})

SHOP_RESPONSE_TYPES: tuple[str, ...] = ("accept_fix", "offer", "disagree", "need_info")
SHOP_RESPONSE_LABELS = {
    "accept_fix": "Agreed to fix it",
    "offer": "Made an offer",
    "disagree": "Disagreed",
    "need_info": "Asked for more information",
}

RULINGS: tuple[str, ...] = ("customer", "shop", "no_fault")
RULING_LABELS = {
    "customer": "In favour of the customer",
    "shop": "In favour of the shop",
    "no_fault": "No fault found",
}
ORDER_ACTIONS: tuple[str, ...] = ("refund", "resend")
SHOP_ACTIONS: tuple[str, ...] = ("warn", "hide_shop", "suspend_owner")
REVIEW_OUTCOMES: tuple[str, ...] = ("action_taken", "no_action")

# A customer is suggested for a "false disputes" flag after this many rulings
# against them within the window.
FLAG_SUGGEST_COUNT = 3
FLAG_SUGGEST_WINDOW = timedelta(days=60)


def reason_label(kind: str, code: str) -> str:
    return REASONS.get(kind, {}).get(code, code)


def report_window() -> timedelta:
    return timedelta(days=settings.support_report_window_days)


def shop_reply_window() -> timedelta:
    return timedelta(hours=settings.support_shop_reply_hours)


def auto_close_window() -> timedelta:
    return timedelta(days=settings.support_auto_close_days)


def order_report_block(
    order_status: str,
    delivered_at: datetime | None,
    last_event_at: datetime | None,
    now: datetime,
) -> str | None:
    """Why an order can't be reported, or None if it can.

    * Not yet delivered/picked up (still open): always reportable — "not
      delivered" can't have a delivery date to count from.
    * Delivered/picked up: only within the window after `delivered_at`.
    * Cancelled (e.g. "I paid but it was cancelled"): within the window after
      the order's last recorded event.
    """
    window = report_window()
    days = settings.support_report_window_days
    if order_status in TERMINAL_STATUSES:
        if delivered_at is not None and now > delivered_at + window:
            return f"The {days}-day window to report a problem with this order has passed."
        return None
    if order_status == "cancelled":
        if last_event_at is not None and now > last_event_at + window:
            return f"The {days}-day window to report a problem with this cancelled order has passed."
        return None
    return None


def clean_photos(photos: list[str] | None) -> list[str]:
    """Validate evidence photo URLs (max N, http(s) only). Raises ValueError."""
    photos = photos or []
    if len(photos) > settings.support_max_photos:
        raise ValueError(f"You can attach up to {settings.support_max_photos} photos.")
    out = []
    for url in photos:
        url = (url or "").strip()
        if not url:
            continue
        if not url.startswith(("https://", "http://")) or len(url) > 2000:
            raise ValueError("Photos must be uploaded images.")
        out.append(url)
    return out
