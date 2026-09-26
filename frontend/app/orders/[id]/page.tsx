"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/apiClient";
import { ReturnRequestModal } from "@/components/account/ReturnRequestModal";
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
  confirmed: "Confirmed",
  preparing: "Preparing",
  ready: "Out for delivery",
  delivered: "Delivered",
  payment_failed: "Payment failed",
};

export default function OrderDetailPage({ params }: { params: { id: string } }) {
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [returns, setReturns] = useState<ReturnRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeItem, setActiveItem] = useState<OrderDetailItem | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  async function load() {
    try {
      const data = await apiFetch(`/orders/${params.id}`);
      setOrder(data);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
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

  // Actively asks Razorpay what really happened to this payment, rather
  // than just re-reading whatever's already in Postgres — see
  // sync-payment-status's docstring on the backend for why this is what
  // actually un-sticks an order that's been sitting at "pending" since
  // before this existed, not only ones placed from now on.
  async function sync() {
    try {
      const data = await apiFetch(`/orders/${params.id}/sync-payment-status`, { method: "POST" });
      setOrder(data);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  // Initial load: reconcile with Razorpay right away rather than a plain
  // read, so landing on this page (including an old bookmark/link to an
  // order that got stuck before sync-payment-status existed) is itself
  // enough to pick up a payment that already succeeded.
  useEffect(() => {
    sync();
    loadReturns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  // Poll every 4s ONLY while status is still "pending", re-syncing with
  // Razorpay on each check (not just re-reading the DB) — payment
  // confirmation can arrive via webhook, via the checkout page's own
  // verify call, or be picked up right here. Each successful load
  // schedules the next check; once status leaves "pending", nothing
  // schedules another one and polling stops itself.
  useEffect(() => {
    if (!order || order.status !== "pending") return;
    const timeoutId = setTimeout(sync, 4000);
    return () => clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order]);

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

  const eligibleForReturn = order.status === "delivered" && isWithinReturnWindow(order.delivered_at);

  return (
    <main className="max-w-2xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Order #{order.id.slice(0, 8)}</h1>
        {order.shop && <p className="text-sm text-gray-500">{order.shop.name}</p>}
        <p className="text-sm mt-2 font-medium">
          {STATUS_LABEL[order.status] ?? order.status}
          {order.status === "pending" && (
            <span className="text-xs text-gray-400 font-normal"> — checking for updates…</span>
          )}
        </p>
        {eligibleForReturn && order.delivered_at && (
          <p className="text-xs text-gray-400 mt-1">
            Eligible for return/exchange until {returnDeadline(order.delivered_at).toLocaleDateString("en-IN")}
          </p>
        )}
      </div>

      <div className="space-y-3">
        {order.items.map((item) => {
          const itemReturns = returnsForItem(item.id);
          const remaining = item.quantity - item.returned_qty;
          return (
            <div key={item.id} className="border-b pb-3 space-y-2">
              <div className="flex justify-between text-sm">
                <span>
                  {item.product_name} × {item.quantity}
                </span>
                <span>₹{item.subtotal}</span>
              </div>

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

      <div className="flex justify-between font-semibold">
        <span>Total</span>
        <span>₹{order.total_amount}</span>
      </div>

      <div className="text-sm">
        <p className="font-medium text-gray-700">Delivery address</p>
        <p className="text-gray-500">{order.delivery_address}</p>
      </div>

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
