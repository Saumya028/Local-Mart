"""
What each order event says, to whom. Pure functions (no database), so the
wording is easy to review and test.

An event can produce a message for the CUSTOMER, for the SHOP team, both, or
neither (e.g. nobody needs a notification for an action they just did
themselves — and the notifier also never notifies the actor).
"""
import html
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Msg:
    title: str
    body: str


def money(value) -> str:
    return f"₹{Decimal(str(value)):,.2f}"


def order_ref(order_id) -> str:
    return "#" + str(order_id).replace("-", "")[:8].upper()


def _how(ctx: dict) -> str:
    return "pickup" if ctx.get("fulfillment") == "pickup" else "delivery"


def _pay_line(ctx: dict) -> str:
    if ctx.get("payment_method") == "upi":
        return f"Pay {ctx['total']} to the shop by UPI, then tap “I’ve paid” on the order page."
    return f"You’ll pay {ctx['total']} in cash at {_how(ctx)}."


_STATUS_TEXT = {
    "preparing": ("{shop} is preparing your order", "Order {ref} has been accepted and is being prepared."),
    "packing": ("Your order is being packed", "{shop} is packing order {ref}."),
    "out_for_delivery": ("Your order is out for delivery", "Order {ref} from {shop} is on its way."),
    "delivered": (
        "Your order was delivered",
        "Order {ref} from {shop} was marked delivered. If something isn’t right, you can request a return from the order page.",
    ),
    "ready_for_pickup": ("Ready for pickup at {shop}", "Order {ref} is ready — you can collect it from the shop now."),
    "picked_up": ("Order picked up", "Order {ref} from {shop} was handed over. Thanks for shopping local!"),
}


def customer_message(kind: str, ctx: dict) -> Msg | None:
    ref, shop = ctx["ref"], ctx["shop_name"]
    role = ctx.get("actor_role")

    if kind == "order_placed":
        if ctx.get("source") == "exchange":
            return None  # covered by the return_completed message
        return Msg(
            f"Order placed with {shop}",
            f"Your order {ref} ({ctx['total']}) was sent to {shop}. {_pay_line(ctx)}",
        )
    if kind == "status_changed":
        text = _STATUS_TEXT.get(ctx.get("to_status") or "")
        if not text:
            return None
        return Msg(text[0].format(shop=shop, ref=ref), text[1].format(shop=shop, ref=ref))
    if kind == "payment_confirmed":
        if ctx.get("auto"):
            return None  # cash collected at hand-over; the "delivered" message already covers it
        return Msg(f"{shop} confirmed your payment", f"Your payment of {ctx['total']} for order {ref} was received.")
    if kind == "payment_rejected":
        return Msg(
            f"{shop} hasn’t received your payment",
            f"The shop couldn’t find your payment for order {ref}. If you did pay, contact the shop; "
            "otherwise open the order to try again or switch to cash.",
        )
    if kind == "order_cancelled" and role != "customer":
        if role == "system":
            return Msg(f"Order {ref} was cancelled", ctx.get("note") or "It was not completed in time.")
        return Msg(
            f"{shop} cancelled order {ref}",
            "If you had already paid, please ask the shop for a refund directly — LocalMart doesn’t hold your money.",
        )
    if kind == "return_approved":
        extra = f" Note from the shop: {ctx['note']}" if ctx.get("note") else ""
        return Msg(f"Your {ctx.get('request_type', 'return')} request was approved", f"{shop} approved your request for {ctx.get('product_name', 'an item')} (order {ref}).{extra}")
    if kind == "return_rejected":
        return Msg(
            f"Your {ctx.get('request_type', 'return')} request was declined",
            f"{shop} declined your request for {ctx.get('product_name', 'an item')} (order {ref}). Reason: {ctx.get('note') or 'not given'}.",
        )
    if kind == "return_completed":
        what = "exchange" if ctx.get("request_type") == "exchange" else "return"
        return Msg(f"Your {what} is complete", f"{shop} marked your {what} for {ctx.get('product_name', 'an item')} (order {ref}) as completed.")
    if kind == "difference_confirmed":
        return Msg(f"{shop} received your top-up", f"The price difference for your exchange (order {ref}) was confirmed.")
    return None


def shop_message(kind: str, ctx: dict) -> Msg | None:
    ref = ctx["ref"]
    buyer = ctx.get("buyer_name") or "A customer"
    role = ctx.get("actor_role")

    if kind == "order_placed":
        if ctx.get("source") == "exchange":
            return None
        n = ctx.get("item_count")
        items = f"{n} item{'s' if n != 1 else ''}, " if n else ""
        method = "UPI" if ctx.get("payment_method") == "upi" else "cash"
        return Msg(
            f"New order — {ctx['total']}",
            f"{buyer} placed order {ref}: {items}{_how(ctx)}, paying by {method}. Please open it and start preparing.",
        )
    if kind == "payment_submitted":
        utr = f" (UTR {ctx['utr']})" if ctx.get("utr") else ""
        return Msg(
            f"Confirm payment — order {ref}",
            f"{buyer} says they paid {ctx['total']} by UPI{utr}. Check your UPI app, then confirm or reject it.",
        )
    if kind == "payment_method_changed":
        if ctx.get("from_method") == ctx.get("to_method"):
            return None
        method = "UPI" if ctx.get("payment_method") == "upi" else "cash"
        return Msg(f"Payment method changed — order {ref}", f"{buyer} switched to paying by {method}.")
    if kind == "order_cancelled":
        if role == "customer":
            return Msg(f"Order {ref} cancelled by the customer", f"{buyer} cancelled before you started on it. Stock has been returned.")
        if role == "system":
            return Msg(f"Order {ref} expired", f"{ctx.get('note') or 'It was not completed in time.'} Stock has been returned.")
        return None
    if kind == "return_requested":
        t = ctx.get("request_type", "return")
        return Msg(
            f"New {t} request — order {ref}",
            f"{buyer} asked for a {t} of {ctx.get('product_name', 'an item')}. Reason: {ctx.get('reason') or 'not given'}.",
        )
    if kind == "return_cancelled":
        return Msg(f"Return request withdrawn — order {ref}", f"{buyer} withdrew their request for {ctx.get('product_name', 'an item')}.")
    if kind == "difference_reported":
        method = "UPI" if ctx.get("payment_method") == "upi" else "cash"
        utr = f" (UTR {ctx['utr']})" if ctx.get("utr") else ""
        return Msg(
            f"Exchange top-up to confirm — order {ref}",
            f"{buyer} will pay the price difference of {ctx.get('amount', '')} by {method}{utr}. Confirm once you have it.",
        )
    return None


FOOTER = (
    "You’re receiving this because of activity on your LocalMart account. "
    "You can turn off email notifications in My Account → Settings."
)


def render_email(msg: Msg, url: str | None) -> tuple[str, str]:
    """(plain text, HTML) bodies. All user-derived text is HTML-escaped."""
    text = msg.title + "\n\n" + msg.body
    if url:
        text += f"\n\nOpen: {url}"
    text += f"\n\n--\n{FOOTER}"

    button = (
        f'<p style="margin:24px 0"><a href="{html.escape(url, quote=True)}" '
        'style="background:#2563eb;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;'
        'font-weight:600;display:inline-block">View details</a></p>'
        if url
        else ""
    )
    page = (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;'
        'padding:24px;color:#111827">'
        f'<h2 style="margin:0 0 12px;font-size:20px">{html.escape(msg.title)}</h2>'
        f'<p style="margin:0;font-size:15px;line-height:1.5">{html.escape(msg.body)}</p>'
        f"{button}"
        f'<p style="margin-top:32px;font-size:12px;color:#6b7280">{html.escape(FOOTER)}</p>'
        "</div>"
    )
    return text, page
