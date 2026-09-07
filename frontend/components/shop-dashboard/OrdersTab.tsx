"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { DashboardOrder, STATUS_TRANSITIONS, formatINR, statusMeta, timeAgo } from "./types";

const FILTERS: { key: string; label: string; statuses?: string[] }[] = [
  { key: "all", label: "All" },
  { key: "confirmed", label: "Pending", statuses: ["confirmed"] },
  { key: "preparing", label: "Preparing", statuses: ["preparing"] },
  { key: "ready", label: "Ready", statuses: ["ready"] },
  { key: "delivered", label: "Delivered", statuses: ["delivered"] },
];

export function OrdersTab({ shopId }: { shopId: string }) {
  const [orders, setOrders] = useState<DashboardOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data: DashboardOrder[] = await apiFetch(`/dashboard/orders?shop_id=${shopId}`);
      setOrders(data);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  async function accept(order: DashboardOrder) {
    // Every actionable order only ever has ONE possible next step — see
    // STATUS_TRANSITIONS. There is no reject/cancel action offered here
    // by design: once an order is paid and in the queue, the shop
    // accepts it and moves it forward.
    const next = STATUS_TRANSITIONS[order.status]?.next;
    if (!next) return;
    setUpdatingId(order.id);
    try {
      await apiFetch(`/dashboard/orders/${order.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUpdatingId(null);
    }
  }

  const filtered = useMemo(() => {
    const activeFilter = FILTERS.find((f) => f.key === filter);
    return orders.filter((o) => {
      if (activeFilter?.statuses && !activeFilter.statuses.includes(o.status)) return false;
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        o.id.toLowerCase().includes(q) ||
        (o.buyer_name ?? "").toLowerCase().includes(q) ||
        o.buyer_email.toLowerCase().includes(q)
      );
    });
  }, [orders, filter, search]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const f of FILTERS) {
      c[f.key] = f.statuses ? orders.filter((o) => f.statuses!.includes(o.status)).length : orders.length;
    }
    return c;
  }, [orders]);

  return (
    <div className="p-8 space-y-4">
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search orders…"
          className="w-full sm:w-72 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex gap-1 bg-gray-50 border border-gray-100 rounded-lg p-1 text-sm overflow-x-auto">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 rounded-md whitespace-nowrap transition-colors ${
                filter === f.key ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"
              }`}
            >
              {f.label} <span className="text-xs text-gray-400">({counts[f.key] ?? 0})</span>
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="bg-white border border-gray-100 rounded-2xl overflow-hidden">
        {loading ? (
          <p className="text-sm text-gray-400 p-6">Loading orders…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-gray-400 p-6">No orders here.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50/50">
                  <th className="px-5 py-3 font-medium">Order ID</th>
                  <th className="px-5 py-3 font-medium">Customer</th>
                  <th className="px-5 py-3 font-medium">Items</th>
                  <th className="px-5 py-3 font-medium">Total</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Time</th>
                  <th className="px-5 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((o) => {
                  const meta = statusMeta(o.status);
                  const action = STATUS_TRANSITIONS[o.status];
                  return (
                    <tr key={o.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/40">
                      <td className="px-5 py-3 text-blue-600 font-medium">#{o.id.slice(0, 8)}</td>
                      <td className="px-5 py-3">
                        <p className="text-gray-800">{o.buyer_name || "—"}</p>
                        <p className="text-xs text-gray-400">{o.buyer_email}</p>
                      </td>
                      <td className="px-5 py-3 text-gray-500">{o.item_count} items</td>
                      <td className="px-5 py-3 font-medium text-gray-800">{formatINR(o.total_amount)}</td>
                      <td className="px-5 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${meta.className}`}>
                          {meta.label}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-gray-400">{timeAgo(o.created_at)}</td>
                      <td className="px-5 py-3">
                        {action ? (
                          <button
                            onClick={() => accept(o)}
                            disabled={updatingId === o.id}
                            className="bg-blue-600 text-white text-xs font-medium rounded-md px-3 py-1.5 disabled:opacity-50"
                          >
                            {updatingId === o.id ? "…" : action.label}
                          </button>
                        ) : (
                          <span className="text-xs text-gray-300">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
