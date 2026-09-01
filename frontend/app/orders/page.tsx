"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/apiClient";

type Order = { id: string; status: string; total_amount: string; created_at: string };

const STATUS_LABEL: Record<string, string> = {
  pending: "Payment pending",
  confirmed: "Confirmed",
  payment_failed: "Payment failed",
};

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/orders")
      .then(setOrders)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading orders…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-10">
        <p className="text-sm text-red-500">{error}</p>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-10 space-y-6">
      <h1 className="text-2xl font-bold">Your orders</h1>

      {orders.length === 0 ? (
        <p className="text-sm text-gray-400">
          No orders yet.{" "}
          <Link href="/" className="underline">
            Start shopping
          </Link>
          .
        </p>
      ) : (
        <div className="space-y-3">
          {orders.map((o) => (
            <Link
              key={o.id}
              href={`/orders/${o.id}`}
              className="block border rounded-lg p-4 hover:border-blue-400 transition"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">Order #{o.id.slice(0, 8)}</p>
                <p className="text-xs text-gray-400">
                  {new Date(o.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center justify-between mt-1">
                <p className="text-xs text-gray-500">{STATUS_LABEL[o.status] ?? o.status}</p>
                <p className="text-sm font-semibold">₹{o.total_amount}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
