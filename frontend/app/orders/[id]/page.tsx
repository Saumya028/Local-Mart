"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";

type OrderItem = { product_name: string; quantity: number; subtotal: string };
type OrderDetail = {
  id: string;
  status: string;
  total_amount: string;
  delivery_address: string;
  created_at: string;
  shop: { id: string; name: string } | null;
  items: OrderItem[];
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Payment pending",
  confirmed: "Confirmed",
  payment_failed: "Payment failed",
};

export default function OrderDetailPage({ params }: { params: { id: string } }) {
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await apiFetch(`/orders/${params.id}`);
      setOrder(data);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  // Initial load.
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  // Poll every 4s ONLY while status is still "pending" — payment
  // confirmation happens asynchronously via the Stripe webhook, so this
  // page has no other way to find out it landed besides checking again.
  // Each successful load schedules the next check; once status leaves
  // "pending", nothing schedules another one and polling stops itself.
  useEffect(() => {
    if (!order || order.status !== "pending") return;
    const timeoutId = setTimeout(load, 4000);
    return () => clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order]);

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
      </div>

      <div className="space-y-2">
        {order.items.map((item, i) => (
          <div key={i} className="flex justify-between text-sm border-b pb-2">
            <span>
              {item.product_name} × {item.quantity}
            </span>
            <span>₹{item.subtotal}</span>
          </div>
        ))}
      </div>

      <div className="flex justify-between font-semibold">
        <span>Total</span>
        <span>₹{order.total_amount}</span>
      </div>

      <div className="text-sm">
        <p className="font-medium text-gray-700">Delivery address</p>
        <p className="text-gray-500">{order.delivery_address}</p>
      </div>
    </main>
  );
}
