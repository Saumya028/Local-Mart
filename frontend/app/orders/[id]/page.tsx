"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiDownload, apiFetch } from "@/lib/apiClient";
import { ReturnRequestModal } from "@/components/account/ReturnRequestModal";
import UpiPayPanel from "@/components/payment/UpiPayPanel";
import { OrderEvent, OrderTimeline } from "@/components/orders/OrderTimeline";
import { DEFAULT_TZ, etaText, inr } from "@/lib/shopInfo";
import { ReviewFormModal } from "@/components/reviews/ReviewFormModal";
import { MyReview, ReviewEligibility, ReviewKind, reviewsPath } from "@/components/reviews/types";
import {
  OrderDetail,
  OrderDetailItem,
  ReturnRequest,
  isWithinReturnWindow,
  returnDeadline,
  returnStatusMeta,
} from "@/components/account/types";

const STATUS_LABEL: Record<string, string> = {
  pending: "Payment pending",
  confirmed: "Order placed",
  preparing: "Preparing",
  packing: "Packing your order",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  ready_for_pickup: "Ready for pickup",
  picked_up: "Picked up",
  payment_failed: "Payment failed",
  cancelled: "Cancelled",
};

export default function OrderDetailPage() {
  // useParams() instead of the `params` prop: in this Next.js version the
  // prop is a Promise, and reading `params.id` off it directly is
  // deprecated (and can come back undefined, which would request
  // /orders/undefined and show "Order not found").
  const params = useParams<{ id: string }>();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [returns, setReturns] = useState<ReturnRequest[]>([]);
  const [timeline, setTimeline] = useState<OrderEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeItem, setActiveItem] = useState<OrderDetailItem | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [cancellingOrder, setCancellingOrder] = useState(false);
  const [reviewTarget, setReviewTarget] = useState<{
    kind: ReviewKind;
    id: string;
    name: string;
    existing: MyReview | null;
  } | null>(null);

  async function load() {
    try {
      const data = await apiFetch(`/orders/${params.id}`);
      setOrder(data);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function loadTimeline() {
    try {
      setTimeline(await apiFetch(`/orders/${params.id}/timeline`));
    } catch {
      // Non-fatal — the order still renders without its history.
    }
  }

  async function loadReturns() {
    try {
      const data = await apiFetch(`/orders/${params.id}/returns`);
      setReturns(data);
    } catch {
      // Non-fatal — the order itself still renders without its return history.
    }
  }

  useEffect(() => {
    load();
    loadReturns();
    loadTimeline();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  // Whenever the order itself changes (a status step, a payment, a poll),
  // its history may have grown too.
  useEffect(() => {
    if (order) loadTimeline();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order?.status, order?.payment_status]);

  // While the customer is waiting on the shop to confirm a UPI payment,
  // quietly re-check every 15s so the page flips to "Paid" on its own.
  useEffect(() => {
    if (!order || order.payment?.status !== "submitted") return;
    const timeoutId = setTimeout(load, 15000);
    return () => clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order]);

  async function paymentAction(path: string, body?: object) {
    setPaymentBusy(true);
    try {
      const data = await apiFetch(`/orders/${params.id}${path}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      setOrder(data);
      setError(null);
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setPaymentBusy(false);
    }
  }

  async function cancelOrder() {
    if (!window.confirm("Cancel this order?")) return;
    setCancellingOrder(true);
    try {
      const data = await apiFetch(`/orders/${params.id}/cancel`, { method: "POST" });
      setOrder(data);
      setActionError(null);
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setCancellingOrder(false);
    }
  }

  async function cancelReturn(returnId: string) {
    setCancellingId(returnId);
    try {
      await apiFetch(`/returns/${returnId}/cancel`, { method: "POST" });
      await Promise.all([load(), loadReturns()]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCancellingId(null);
    }
  }

  // Opens the review form for a product or this order's shop. Loads the
  // customer's existing review first (if any) so the same button edits it.
  async function openReview(kind: ReviewKind, id: string, name: string) {
    setActionError(null);
    try {
      const e: ReviewEligibility = await apiFetch(`${reviewsPath(kind, id)}/mine`);
      if (!e.can_review) {
        setActionError(e.reason ?? "You can't review this yet.");
        return;
      }
      setReviewTarget({ kind, id, name, existing: e.review });
    } catch (err) {
      setActionError((err as Error).message);
    }
  }

  function returnsForItem(itemId: string) {
    return returns.filter((r) => r.order_item_id === itemId);
  }

  if (error) {
    return (
      <main className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-red-500">{error}</p>
      </main>
    );
  }

  if (!order) {
    return (
      <main className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  const isPickup = order.fulfillment_type === "pickup";
  const fulfilled = order.status === "delivered" || order.status === "picked_up";
  const eligibleForReturn =
    (order.status === "delivered" || order.status === "picked_up") && isWithinReturnWindow(order.delivered_at);

  return (
    <main className="max-w-2xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Order #{order.id.slice(0, 8)}</h1>
        {order.shop && <p className="text-sm text-gray-500">{order.shop.name}</p>}
        <p className="text-sm mt-2 font-medium">
          {STATUS_LABEL[order.status] ?? order.status}
        </p>
        {!fulfilled && order.status !== "cancelled" && etaText(order, order.shop?.timezone || DEFAULT_TZ) && (
          <p className="text-sm text-blue-700 mt-1">
            {order.slot_start ? "Scheduled " : "Expected "}
            {etaText(order, order.shop?.timezone || DEFAULT_TZ)}
          </p>
        )}
        {order.shop?.contact_phone && order.status !== "cancelled" && (
          <p className="text-xs text-gray-500 mt-1">
            Questions about this order?{" "}
            <a href={`tel:${order.shop.contact_phone}`} className="text-blue-600 hover:underline">
              Call {order.shop.name}
            </a>
          </p>
        )}
        {eligibleForReturn && order.delivered_at && (
          <p className="text-xs text-gray-400 mt-1">
            Eligible for return/exchange until {returnDeadline(order.delivered_at).toLocaleDateString("en-IN")}
          </p>
        )}
        {order.delivery_proof_photo_url && (
          <a
            href={order.delivery_proof_photo_url}
            target="_blank"
            rel="noreferrer"
            className="inline-block text-xs text-blue-600 underline mt-2"
          >
            View proof of delivery
          </a>
        )}
      </div>

      {actionError && <p className="text-sm text-red-500">{actionError}</p>}

      {order.payment && order.status !== "cancelled" && (
        <div className="space-y-3">
          {order.payment.method === "upi" ? (
            <>
              <UpiPayPanel
                amount={order.payment.amount}
                payeeName={order.payment.payee_name}
                upiId={order.payment.upi_id}
                upiQrUrl={order.payment.upi_qr_url}
                upiLink={order.payment.upi_link}
                status={order.payment.status}
                payerReference={order.payment.payer_reference}
                busy={paymentBusy}
                onMarkPaid={(ref) => paymentAction("/payment/mark-paid", { payer_reference: ref || null })}
              />
              {order.payment.status !== "paid" && order.payment.shop_accepts_cash && (
                <button
                  onClick={() => paymentAction("/payment/change-method", { method: "cash" })}
                  disabled={paymentBusy}
                  className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                >
                  Pay cash {isPickup ? "at pickup" : "on delivery"} instead
                </button>
              )}
            </>
          ) : (
            <div
              className={`rounded-xl text-sm px-4 py-3 ${
                order.payment.status === "paid" ? "bg-emerald-50 text-emerald-700" : "bg-gray-50 text-gray-700"
              }`}
            >
              {order.payment.status === "paid"
                ? `₹${order.payment.amount} paid in cash.`
                : `Pay ₹${order.payment.amount} in cash ${isPickup ? "when you pick up your order" : "when your order is delivered"}.`}
              {order.payment.status !== "paid" && order.payment.shop_accepts_upi && (
                <button
                  onClick={() => paymentAction("/payment/change-method", { method: "upi" })}
                  disabled={paymentBusy}
                  className="block text-xs text-blue-600 hover:underline mt-1 disabled:opacity-50"
                >
                  Pay by UPI instead
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {order.status === "confirmed" && order.payment && ["unpaid"].includes(order.payment.status) && (
        <button
          onClick={cancelOrder}
          disabled={cancellingOrder}
          className="text-xs text-red-500 hover:underline disabled:opacity-50"
        >
          {cancellingOrder ? "Cancelling…" : "Cancel this order"}
        </button>
      )}

      <div className="space-y-3">
        {order.items.map((item) => {
          const itemReturns = returnsForItem(item.id);
          const remaining = item.quantity - item.returned_qty;
          return (
            <div key={item.id} className="border-b pb-3 space-y-2">
              <div className="flex justify-between text-sm">
                <span>
                  {item.product_name}
                  {item.unit_label ? ` (${item.unit_label})` : ""} × {item.quantity}
                </span>
                <span>₹{item.subtotal}</span>
              </div>

              {fulfilled && (
                <button
                  onClick={() => openReview("product", item.product_id, item.product_name)}
                  className="text-xs text-amber-600 hover:underline block"
                >
                  {item.review_id ? "★ Edit your review" : "☆ Rate this product"}
                </button>
              )}

              {eligibleForReturn && remaining > 0 && (
                <button
                  onClick={() => setActiveItem(item)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Return or exchange this item
                </button>
              )}

              {itemReturns.map((r) => {
                const meta = returnStatusMeta(r.status);
                return (
                  <div key={r.id} className="bg-gray-50 rounded-lg p-3 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-700">
                        {r.request_type === "exchange" ? "Exchange" : "Return"} · {r.quantity} unit(s)
                      </span>
                      <span className={`px-2 py-0.5 rounded-full font-medium ${meta.className}`}>
                        {meta.label}
                      </span>
                    </div>
                    <p className="text-gray-500">{r.reason}</p>
                    {r.request_type === "exchange" && r.exchange_product_name && (
                      <p className="text-gray-500">For: {r.exchange_product_name}</p>
                    )}
                    {r.request_type === "exchange" && parseFloat(r.price_difference) > 0.004 && (
                      <p className="text-amber-600 font-medium">
                        {r.difference_paid
                          ? `₹${r.price_difference} difference paid`
                          : `₹${r.price_difference} more — pay from My Returns once approved`}
                      </p>
                    )}
                    {r.request_type === "exchange" && parseFloat(r.price_difference) < -0.004 && (
                      <p className="text-emerald-600 font-medium">
                        ₹{Math.abs(parseFloat(r.price_difference)).toFixed(2)} refund due
                      </p>
                    )}
                    {r.new_order_id && (
                      <Link href={`/orders/${r.new_order_id}`} className="text-blue-600 hover:underline block">
                        Track replacement order
                      </Link>
                    )}
                    {r.shop_note && <p className="text-gray-500">Shop: {r.shop_note}</p>}
                    {r.status === "requested" && (
                      <button
                        onClick={() => cancelReturn(r.id)}
                        disabled={cancellingId === r.id}
                        className="text-red-500 hover:underline disabled:opacity-50"
                      >
                        {cancellingId === r.id ? "Cancelling…" : "Cancel request"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      <div className="space-y-1 text-sm">
        {(Number(order.delivery_fee ?? 0) > 0 || Number(order.tax_amount ?? 0) > 0) && (
          <>
            <div className="flex justify-between text-gray-600">
              <span>Items{Number(order.tax_amount ?? 0) > 0 ? " (excl. GST)" : ""}</span>
              <span>{inr(order.subtotal_amount)}</span>
            </div>
            {Number(order.tax_amount ?? 0) > 0 && (
              <div className="flex justify-between text-gray-600">
                <span>GST</span>
                <span>{inr(order.tax_amount)}</span>
              </div>
            )}
            {Number(order.delivery_fee ?? 0) > 0 && (
              <div className="flex justify-between text-gray-600">
                <span>Delivery</span>
                <span>{inr(order.delivery_fee)}</span>
              </div>
            )}
          </>
        )}
        <div className="flex justify-between font-semibold text-base">
          <span>Total</span>
          <span>₹{order.total_amount}</span>
        </div>
        {Number(order.savings_amount ?? 0) > 0 && (
          <p className="text-xs text-emerald-700 text-right">You saved {inr(order.savings_amount)} on this order</p>
        )}
        {order.status !== "cancelled" && (
          <div className="text-right pt-1">
            <button
              type="button"
              onClick={() =>
                apiDownload(`/orders/${order.id}/invoice`, "invoice.pdf").catch(() =>
                  alert("Couldn't download the invoice. Please try again."),
                )
              }
              className="text-sm text-blue-600 hover:underline"
            >
              Download invoice (PDF)
            </button>
          </div>
        )}
      </div>

      {fulfilled && order.shop && (
        <div className="rounded-xl bg-amber-50 px-4 py-3 flex items-center justify-between gap-3">
          <p className="text-sm text-amber-800">
            {order.shop_review_id ? `Your review of ${order.shop.name}` : `How was ${order.shop.name}?`}
          </p>
          <button
            onClick={() => openReview("shop", order.shop!.id, order.shop!.name)}
            className="text-sm font-medium text-amber-700 hover:underline whitespace-nowrap"
          >
            {order.shop_review_id ? "Edit review" : "Rate this shop"}
          </button>
        </div>
      )}

      <div className="text-sm">
        {isPickup ? (
          <>
            <p className="font-medium text-gray-700">Pickup from {order.shop?.name ?? "the shop"}</p>
            <p className="text-gray-500">
              {order.shop?.address_line1 ? `${order.shop.address_line1}, ${order.shop.city ?? ""}` : "Address on request from the shop."}
            </p>
          </>
        ) : (
          <>
            <p className="font-medium text-gray-700">Delivery address</p>
            <p className="text-gray-500">{order.delivery_address}</p>
          </>
        )}
      </div>

      <section aria-labelledby="order-history-heading" className="pt-2">
        <h2 id="order-history-heading" className="text-sm font-semibold text-gray-900 mb-3">
          Order history
        </h2>
        <OrderTimeline events={timeline} />
      </section>

      {reviewTarget && (
        <ReviewFormModal
          kind={reviewTarget.kind}
          targetId={reviewTarget.id}
          targetName={reviewTarget.name}
          existing={reviewTarget.existing}
          onClose={() => setReviewTarget(null)}
          onSaved={() => {
            setReviewTarget(null);
            load();
          }}
        />
      )}

      {activeItem && order.shop && (
        <ReturnRequestModal
          orderId={order.id}
          shopId={order.shop.id}
          item={activeItem}
          onClose={() => setActiveItem(null)}
          onSubmitted={() => {
            setActiveItem(null);
            load();
            loadReturns();
          }}
        />
      )}
    </main>
  );
}
