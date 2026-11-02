"""
Which notifications are ALSO sent by email.

Every notification appears in the in-app bell. Email is reserved for the few
that matter enough to interrupt someone, and the default is NO: a notification
kind that isn't listed here is bell-only, so adding a new kind can never start
spamming inboxes by accident.

Product decision (Oct 2026): emailing every status update was noise.

  customer   order confirmation, and a one-time welcome at first signup
  shop       a customer's return request, and an exchange top-up reported

Everything else — order progress (preparing / packing / out for delivery /
delivered), ETA changes, payment updates, new-order alerts to the shop, stock
alerts, return outcomes, customer support — stays in the bell (and, for orders,
on the order page and timeline). A person who has switched email off in
Settings still gets nothing emailed, whatever is listed here.

Promotional email is intentionally not built yet; when it is, it must be
opt-in (see the product notes in the README).
"""

# (audience, notification kind). Audience matters: "order_placed" is emailed to
# the customer (their confirmation) but NOT to the shop.
EMAILED: frozenset[tuple[str, str]] = frozenset(
    {
        ("customer", "order_placed"),
        ("customer", "welcome"),
        ("shop", "return_requested"),
        ("shop", "difference_reported"),
    }
)


def should_email(audience: str, kind: str) -> bool:
    return (audience, kind) in EMAILED
