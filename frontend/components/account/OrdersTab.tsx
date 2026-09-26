"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/apiClient";
import { AccountOrder, OrderDetail, formatDate, orderStatusMeta } from "./types";

export function OrdersTab({ onOrdersLoaded }: { onOrdersLoaded?: (orders: AccountOrder[]) => void }) {
  const [orders, setOrders] = useState<AccountOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reorderingId, setReorderingId] = useState<string | null>(null);
  const [reorderMsg, setReorderMsg] = useState<{ id: string; text: string } | null>(null);

  useEffect(() => {
    apiFetch("/orders")
      .then((data: AccountOrder[]) => {
        setOrders(data);
        onOrdersLoaded?.(data);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function reorder(order: AccountOrder) {
    setReorderingId(order.id);
    setReorderMsg(null);
    try {
      const detail: OrderDetail = await apiFetch(`/orders/${order.id}`);
      let added = 0;
      let skipped = 0;
      for (const item of detail.items) {
        try {
          await apiFetch("/cart/items", {
            method: "POST",
            body: JSON.stringify({ product_id: item.product_id, quantity: item.quantity }),
          });
          added += 1;
        } catch {
          skipped += 1;
        }
      }
      setReorderMsg({
        id: order.id,
        text:
          skipped === 0
            ? `Added ${added} item${added === 1 ? "" : "s"} to your cart.`
            : `Added ${added}, ${skipped} no longer available.`,
      });
    } catch (err) {
      setReorderMsg({ id: order.id, text: (err as Error).message });
    } finally {
      setReorderingId(null);
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading orders…</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (orders.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
        <p className="text-sm text-gray-500">You haven&apos;t placed any orders yet.</p>
        <Link href="/search" className="text-sm text-blue-600 underline mt-2 inline-block">
          Start shopping
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {orders.map((order) => {
        const status = orderStatusMeta(order.status);
        return (
          <div
            key={order.id}
            className="bg-white rounded-2xl border border-gray-100 p-5 flex items-center justify-between gap-4"
          >
            <div className="flex items-center gap-4 min-w-0">
              <div className="w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
                <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
                  <path d="M3 6.5 10 3l7 3.5-7 3.5-7-3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                  <path d="M3 6.5V14l7 3.5 7-3.5V6.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                </svg>
              </div>
              <div className="min-w-0">
                <Link href={`/orders/${order.id}`} className="font-semibold text-gray-900 hover:underline truncate block">
                  {order.shop_name ?? "Shop"}
                </Link>
                <p className="text-xs text-gray-400 truncate">
                  #{order.id.slice(0, 8).toUpperCase()} · {order.item_count} item{order.item_count === 1 ? "" : "s"} · ₹
                  {order.total_amount}
                </p>
                <p className="text-xs text-gray-300">{formatDate(order.created_at)}</p>
              </div>
            </div>
            <div className="flex flex-col items-end gap-1.5 shrink-0">
              <span className={`text-xs font-medium rounded-full px-2.5 py-1 whitespace-nowrap ${status.className}`}>
                {status.label}
              </span>
              {order.status === "delivered" && (
                <button
                  onClick={() => reorder(order)}
                  disabled={reorderingId === order.id}
                  className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                >
                  {reorderingId === order.id ? "Adding…" : "Reorder"}
                </button>
              )}
              {order.status === "delivered" && (
                <Link href={`/orders/${order.id}`} className="text-xs text-gray-500 hover:underline">
                  Return / Exchange
                </Link>
              )}
              {reorderMsg?.id === order.id && (
                <p className="text-xs text-gray-400 max-w-[10rem] text-right">{reorderMsg.text}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
