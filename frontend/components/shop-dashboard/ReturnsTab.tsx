"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import {
  DashboardReturn,
  RETURN_STATUS_TRANSITIONS,
  formatINR,
  returnStatusMeta,
  timeAgo,
} from "./types";

const FILTERS: { key: string; label: string; statuses?: string[] }[] = [
  { key: "all", label: "All" },
  { key: "requested", label: "Needs review", statuses: ["requested"] },
  { key: "approved", label: "Approved", statuses: ["approved"] },
  { key: "completed", label: "Completed", statuses: ["completed"] },
  { key: "rejected", label: "Rejected", statuses: ["rejected"] },
];

export function ReturnsTab({ shopId }: { shopId: string }) {
  const [returns, setReturns] = useState<DashboardReturn[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectNote, setRejectNote] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data: DashboardReturn[] = await apiFetch(`/dashboard/returns?shop_id=${shopId}`);
      setReturns(data);
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

  async function setStatus(id: string, status: string, shopNote?: string) {
    setUpdatingId(id);
    try {
      await apiFetch(`/dashboard/returns/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status, shop_note: shopNote ?? null }),
      });
      setRejectingId(null);
      setRejectNote("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUpdatingId(null);
    }
  }

  const filtered = useMemo(() => {
    const activeFilter = FILTERS.find((f) => f.key === filter);
    if (!activeFilter?.statuses) return returns;
    return returns.filter((r) => activeFilter.statuses!.includes(r.status));
  }, [returns, filter]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const f of FILTERS) {
      c[f.key] = f.statuses ? returns.filter((r) => f.statuses!.includes(r.status)).length : returns.length;
    }
    return c;
  }, [returns]);

  return (
    <div className="p-8 space-y-4">
      <div className="flex gap-1 bg-gray-50 border border-gray-100 rounded-lg p-1 text-sm overflow-x-auto w-fit">
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

      {error && <p className="text-sm text-red-500">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-400">Loading return requests…</p>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-gray-100 rounded-2xl p-6">
          <p className="text-sm text-gray-400">No return or exchange requests here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((r) => {
            const meta = returnStatusMeta(r.status);
            const awaitingDifferencePayment =
              r.request_type === "exchange" && parseFloat(r.price_difference) > 0.004 && !r.difference_paid;
            // The backend rejects "completed" with a 400 in this state
            // anyway (see update_return_status) — filtering it out here
            // just means the shop owner never sees a button that would
            // only fail; the price-difference note above already
            // explains why.
            const actions = (RETURN_STATUS_TRANSITIONS[r.status] ?? []).filter(
              (a) => !(a.next === "completed" && awaitingDifferencePayment)
            );
            return (
              <div key={r.id} className="bg-white border border-gray-100 rounded-2xl p-5 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-gray-900">{r.product_name ?? "Item"}</p>
                    <p className="text-xs text-gray-400">
                      {r.buyer_name || r.buyer_email} · Order #{r.order_id.slice(0, 8)} ·{" "}
                      {r.request_type === "exchange" ? "Exchange" : "Return"} · {r.quantity} unit(s) ·{" "}
                      {timeAgo(r.created_at)}
                    </p>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${meta.className}`}>
                    {meta.label}
                  </span>
                </div>

                <p className="text-sm text-gray-600">Reason: {r.reason}</p>
                {r.comment && <p className="text-sm text-gray-500">&ldquo;{r.comment}&rdquo;</p>}
                {r.request_type === "exchange" && r.exchange_product_name && (
                  <p className="text-sm text-gray-600">Wants instead: {r.exchange_product_name}</p>
                )}
                {r.request_type === "return" && (
                  <p className="text-sm text-gray-600">Refund due: {formatINR(r.refund_amount)}</p>
                )}
                {r.request_type === "exchange" && parseFloat(r.price_difference) > 0.004 && (
                  <p
                    className={`text-sm rounded-lg px-3 py-2 ${
                      r.difference_paid ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                    }`}
                  >
                    Replacement costs {formatINR(r.price_difference)} more —{" "}
                    {r.difference_paid
                      ? "the customer has paid this."
                      : "waiting on the customer to pay this before you can complete the exchange."}
                  </p>
                )}
                {r.request_type === "exchange" && parseFloat(r.price_difference) < -0.004 && (
                  <p className="text-sm rounded-lg px-3 py-2 bg-amber-50 text-amber-700">
                    Replacement costs {formatINR(Math.abs(parseFloat(r.price_difference)))} less —
                    refund that to the customer when you complete this.
                  </p>
                )}
                {r.new_order_id && (
                  <p className="text-sm text-gray-500">
                    New order created: #{r.new_order_id.slice(0, 8)} — find it in your Orders tab.
                  </p>
                )}
                {r.shop_note && (
                  <p className="text-sm text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
                    Your note: {r.shop_note}
                  </p>
                )}

                {rejectingId === r.id ? (
                  <div className="space-y-2 pt-1">
                    <textarea
                      value={rejectNote}
                      onChange={(e) => setRejectNote(e.target.value)}
                      placeholder="Explain why you're declining this request…"
                      rows={2}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => setStatus(r.id, "rejected", rejectNote)}
                        disabled={updatingId === r.id || !rejectNote.trim()}
                        className="bg-red-600 text-white text-xs font-medium rounded-md px-3 py-1.5 disabled:opacity-50"
                      >
                        {updatingId === r.id ? "…" : "Confirm rejection"}
                      </button>
                      <button
                        onClick={() => {
                          setRejectingId(null);
                          setRejectNote("");
                        }}
                        className="text-xs text-gray-500 px-3 py-1.5"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  actions.length > 0 && (
                    <div className="flex gap-2 pt-1">
                      {actions.map((a) => (
                        <button
                          key={a.next}
                          onClick={() =>
                            a.next === "rejected" ? setRejectingId(r.id) : setStatus(r.id, a.next)
                          }
                          disabled={updatingId === r.id}
                          className={`text-xs font-medium rounded-md px-3 py-1.5 disabled:opacity-50 ${
                            a.next === "rejected"
                              ? "border border-red-200 text-red-600"
                              : "bg-blue-600 text-white"
                          }`}
                        >
                          {updatingId === r.id ? "…" : a.label}
                        </button>
                      ))}
                    </div>
                  )
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
