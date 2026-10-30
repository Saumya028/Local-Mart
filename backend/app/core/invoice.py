"""
GST invoice: numbering, data assembly and PDF rendering.

Numbers look like  INV/2526/00042  (financial year + a per-shop running
sequence), well inside the 16-character limit GST rules set, and unique per
shop. Orders placed before invoicing existed get a number the first time an
invoice is requested.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.gst import InvoiceLine, amount_in_words, build_line, financial_year, is_inter_state, money
from app.models import Order, OrderItem, Product, Profile, Shop


async def next_invoice_number(db: AsyncSession, shop: Shop, now: datetime) -> str:
    """Atomically take the shop's next invoice number."""
    seq = (
        await db.execute(
            update(Shop).where(Shop.id == shop.id).values(invoice_seq=Shop.invoice_seq + 1).returning(Shop.invoice_seq)
        )
    ).scalar_one()
    try:
        local = now.astimezone(ZoneInfo(shop.timezone or "Asia/Kolkata"))
    except Exception:
        local = now
    return f"INV/{financial_year(local)}/{seq:05d}"


@dataclass
class InvoiceData:
    number: str
    issued_at: datetime
    title: str  # "TAX INVOICE" | "INVOICE"
    seller_name: str
    seller_address: str
    seller_gstin: str | None
    seller_phone: str | None
    buyer_name: str
    buyer_gstin: str | None
    buyer_address: str | None
    inter_state: bool
    order_ref: str
    payment_method: str | None
    lines: list[InvoiceLine] = field(default_factory=list)
    delivery_fee: Decimal = Decimal("0.00")

    @property
    def taxable_total(self) -> Decimal:
        return sum((l.taxable for l in self.lines), Decimal("0.00"))

    @property
    def cgst_total(self) -> Decimal:
        return sum((l.cgst for l in self.lines), Decimal("0.00"))

    @property
    def sgst_total(self) -> Decimal:
        return sum((l.sgst for l in self.lines), Decimal("0.00"))

    @property
    def igst_total(self) -> Decimal:
        return sum((l.igst for l in self.lines), Decimal("0.00"))

    @property
    def grand_total(self) -> Decimal:
        return self.taxable_total + self.cgst_total + self.sgst_total + self.igst_total + self.delivery_fee


async def build_invoice_data(db: AsyncSession, order: Order) -> InvoiceData:
    """Assemble an order's invoice. Assigns the invoice number on first use."""
    shop = (await db.execute(select(Shop).where(Shop.id == order.shop_id))).scalar_one()
    buyer = (await db.execute(select(Profile).where(Profile.id == order.user_id))).scalar_one()

    if not order.invoice_number:
        order.invoice_number = await next_invoice_number(db, shop, datetime.now(timezone.utc))
        await db.commit()

    rows = (
        await db.execute(
            select(OrderItem, Product.name)
            .join(Product, Product.id == OrderItem.product_id)
            .where(OrderItem.order_id == order.id)
            .order_by(Product.name)
        )
    ).all()

    inter = is_inter_state(shop.gstin, order.buyer_gstin)
    lines = []
    for item, name in rows:
        desc = f"{name} ({item.unit_label})" if item.unit_label else name
        lines.append(build_line(desc, item.hsn_code, item.quantity, item.unit_price, item.gst_rate, inter))

    from app.models import Payment  # local: avoid import cycle at module load

    payment = (await db.execute(select(Payment).where(Payment.order_id == order.id))).scalar_one_or_none()
    address = ", ".join(p for p in (shop.address_line1, shop.city) if p)
    buyer_name = order.buyer_business_name or buyer.full_name or buyer.email
    return InvoiceData(
        number=order.invoice_number,
        issued_at=order.created_at,
        title="TAX INVOICE" if shop.gstin else "INVOICE",
        seller_name=shop.legal_name or shop.name,
        seller_address=address,
        seller_gstin=shop.gstin,
        seller_phone=shop.contact_phone,
        buyer_name=buyer_name,
        buyer_gstin=order.buyer_gstin,
        buyer_address=order.delivery_address,
        inter_state=inter,
        order_ref=str(order.id)[:8],
        payment_method=payment.method if payment else None,
        lines=lines,
        delivery_fee=money(order.delivery_fee or 0),
    )


def _fmt(x: Decimal) -> str:
    return f"{x:,.2f}"


def render_invoice_pdf(inv: InvoiceData) -> bytes:
    """A4 invoice. Uses the built-in Helvetica (no ₹ glyph), so amounts read "Rs."."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"{inv.title.title()} {inv.number}", author=inv.seller_name,
    )
    ss = getSampleStyleSheet()
    base = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=8.5, leading=11)
    small = ParagraphStyle("s", parent=base, fontSize=7.5, textColor=colors.HexColor("#6b7280"))
    bold = ParagraphStyle("bb", parent=base, fontName="Helvetica-Bold")
    h1 = ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=15, leading=18)
    right = ParagraphStyle("r", parent=base, alignment=2)
    right_b = ParagraphStyle("rb", parent=bold, alignment=2)
    E = lambda t: escape(str(t or ""))  # noqa: E731

    story = []
    head = Table(
        [[Paragraph(inv.title, h1),
          Paragraph(f"<b>Invoice No:</b> {E(inv.number)}<br/><b>Date:</b> {inv.issued_at.astimezone(ZoneInfo('Asia/Kolkata')):%d %b %Y}"
                    f"<br/><b>Order:</b> #{E(inv.order_ref)}", right)]],
        colWidths=[95 * mm, 85 * mm],
    )
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [head, Spacer(1, 4 * mm)]

    seller = f"<b>{E(inv.seller_name)}</b><br/>{E(inv.seller_address)}"
    if inv.seller_phone:
        seller += f"<br/>Phone: {E(inv.seller_phone)}"
    seller += f"<br/><b>GSTIN:</b> {E(inv.seller_gstin)}" if inv.seller_gstin else "<br/>GSTIN: not registered"
    buyer = f"<b>{E(inv.buyer_name)}</b>"
    if inv.buyer_address:
        buyer += f"<br/>{E(inv.buyer_address)}"
    if inv.buyer_gstin:
        buyer += f"<br/><b>GSTIN:</b> {E(inv.buyer_gstin)}"
    parties = Table(
        [[Paragraph("SOLD BY", small), Paragraph("BILLED TO", small)], [Paragraph(seller, base), Paragraph(buyer, base)]],
        colWidths=[90 * mm, 90 * mm],
    )
    parties.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("LINEAFTER", (0, 0), (0, -1), 0.5, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [parties, Spacer(1, 4 * mm)]

    tax_cols = ["IGST"] if inv.inter_state else ["CGST", "SGST"]
    header = ["#", "Item", "HSN", "Qty", "Rate", "Taxable"] + [f"{c}" for c in tax_cols] + ["Total"]
    data = [[Paragraph(f"<b>{h}</b>", right if i >= 3 else base) for i, h in enumerate(header)]]
    for n, l in enumerate(inv.lines, 1):
        half = f"{l.rate / 2:g}%" if not inv.inter_state else f"{l.rate:g}%"
        cells = [
            Paragraph(str(n), base), Paragraph(E(l.description), base), Paragraph(E(l.hsn or "-"), base),
            Paragraph(str(l.qty), right), Paragraph(_fmt(l.unit_price), right), Paragraph(_fmt(l.taxable), right),
        ]
        if inv.inter_state:
            cells.append(Paragraph(f"{_fmt(l.igst)}<br/><font size=6.5 color='#6b7280'>{half}</font>", right))
        else:
            cells.append(Paragraph(f"{_fmt(l.cgst)}<br/><font size=6.5 color='#6b7280'>{half}</font>", right))
            cells.append(Paragraph(f"{_fmt(l.sgst)}<br/><font size=6.5 color='#6b7280'>{half}</font>", right))
        cells.append(Paragraph(_fmt(l.total), right))
        data.append(cells)
    fixed = [8, None, 18, 10, 17, 20] + [20] * len(tax_cols) + [22]
    avail = 180 - sum(w for w in fixed if w)
    widths = [(w if w else avail) * mm for w in fixed]
    items = Table(data, colWidths=widths, repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [items, Spacer(1, 3 * mm)]

    rows = [["Taxable value", _fmt(inv.taxable_total)]]
    if inv.inter_state:
        rows.append(["IGST", _fmt(inv.igst_total)])
    else:
        rows += [["CGST", _fmt(inv.cgst_total)], ["SGST", _fmt(inv.sgst_total)]]
    if inv.delivery_fee > 0:
        rows.append(["Delivery charge", _fmt(inv.delivery_fee)])
    rows.append(["Total (Rs.)", _fmt(inv.grand_total)])
    tot = Table(
        [[Paragraph(a, right_b if i == len(rows) - 1 else right), Paragraph(b, right_b if i == len(rows) - 1 else right)]
         for i, (a, b) in enumerate(rows)],
        colWidths=[40 * mm, 30 * mm], hAlign="RIGHT",
    )
    tot.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black)]))
    story += [tot, Spacer(1, 3 * mm), Paragraph(f"<b>Amount in words:</b> {amount_in_words(inv.grand_total)}", base)]
    if inv.payment_method:
        story.append(Paragraph(f"Payment: {'UPI' if inv.payment_method == 'upi' else 'Cash'} (paid directly to the seller)", base))
    story += [
        Spacer(1, 6 * mm),
        Paragraph(
            "This is a computer-generated invoice and does not require a signature. "
            + ("Delivery charge is shown without GST." if inv.delivery_fee > 0 else ""),
            small,
        ),
    ]
    doc.build(story)
    return buf.getvalue()
