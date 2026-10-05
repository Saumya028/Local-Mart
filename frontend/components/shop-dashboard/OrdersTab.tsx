"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { uploadDeliveryProof } from "@/lib/deliveryProofUpload";
import {
  DashboardOrder,
  PROOF_REQUIRED_STATUSES,
  formatINR,
  statusMeta,
  timeAgo,
  transitionsForFulfillment,
} from "./types";

const FILTERS: { key: string; label: string; statuses?: string[] }[] = [
  { key: "all", label: "All" },
  { key: "confirmed", label: "Pending", statuses: ["confirmed"] },
  { key: "preparing", label: "Preparing", statuses: ["preparing"] },
  { key: "packing", label: "Packing", statuses: ["packing"] },
  { key: "out_for_delivery", label: "Out for Delivery", statuses: ["out_for_delivery"] },
  { key: "ready_for_pickup", label: "Ready for Pickup", statuses: ["ready_for_pickup"] },
  { key: "delivered", label: "Delivered", statuses: ["delivered"] },
  { key: "picked_up", label: "Picked Up", statuses: ["picked_up"] },
  { key: "cancelled", label: "Cancelled", statuses: ["cancelled"] },
];

// Mirrors backend SHOP_CANCELABLE_FROM — a shop can cancel any time
// before the order leaves for delivery / is ready for pickup.
const SHOP_CANCELABLE = new Set(["confirmed", "preparing", "packing"]);

export function OrdersTab({ shopId }: { shopId: string }) {
  const { profile } = useAuth();
  // Confirming/rejecting payments and cancelling orders is for the shop
  // owner and managers — a delivery hire only moves orders along (the
  // backend enforces this too).
  const canManagePayments = profile?.role !== "delivery_partner";
  const [orders, setOrders] = useState<DashboardOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  // The order currently in the "take a delivery photo" modal — separate
  // from updatingId, since opening this modal doesn't call the API yet.
  const [proofOrder, setProofOrder] = useState<DashboardOrder | null>(null);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofPreview, setProofPreview] = useState<string | null>(null);
  const [proofError, setProofError] = useState<string | null>(null);
  const [submittingProof, setSubmittingProof] = useState(false);

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

  async function advance(order: DashboardOrder, proofPhotoUrl?: string) {
    const next = transitionsForFulfillment(order.fulfillment_type)[order.status]?.next;
    if (!next) return;
    setUpdatingId(order.id);
    try {
      await apiFetch(`/dashboard/orders/${order.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: next, delivery_proof_photo_url: proofPhotoUrl ?? null }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUpdatingId(null);
    }
  }

  // Payment goes straight from the customer to this shop, so the shop is
  // the one who confirms (or disputes) that the money arrived.
  async function orderAction(order: DashboardOrder, path: string, confirmMsg?: string) {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setUpdatingId(order.id);
    try {
      await apiFetch(`/dashboard/orders/${order.id}${path}`, { method: "POST" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUpdatingId(null);
    }
  }

  function accept(order: DashboardOrder) {
    // Every actionable order only ever has ONE possible next step,
    // picked from whichever of DELIVERY_STATUS_TRANSITIONS /
    // PICKUP_STATUS_TRANSITIONS matches this order's OWN
    // fulfillment_type. There is no reject/cancel action offered here by
    // design: once an order is paid and in the queue, the shop accepts
    // it and moves it forward. The one exception is the final
    // "delivered" step (delivery orders only), which needs a proof
    // photo first — that opens a modal instead of calling the API
    // straight away. A pickup order's final step ("Mark Picked Up")
    // needs no photo — the shop's own staff hands it over in person and
    // IS the witness — so it goes straight through advance() below.
    const next = transitionsForFulfillment(order.fulfillment_type)[order.status]?.next;
    if (next && PROOF_REQUIRED_STATUSES.has(next)) {
      setProofOrder(order);
      setProofFile(null);
      setProofPreview(null);
      setProofError(null);
      return;
    }
    advance(order);
  }

  function closeProofModal() {
    if (proofPreview) URL.revokeObjectURL(proofPreview);
    setProofOrder(null);
    setProofFile(null);
    setProofPreview(null);
    setProofError(null);
  }

  function pickProofFile(file: File | null) {
    if (proofPreview) URL.revokeObjectURL(proofPreview);
    setProofFile(file);
    setProofPreview(file ? URL.createObjectURL(file) : null);
  }

  async function submitProof() {
    if (!proofOrder || !proofFile || !profile) return;
    setSubmittingProof(true);
    setProofError(null);
    try {
      const url = await uploadDeliveryProof(profile.id, proofFile);
      await advance(proofOrder, url);
      closeProofModal();
    } catch (err) {
      setProofError((err as Error).message);
    } finally {
      setSubmittingProof(false);
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

  // Shared by the desktop table row and the mobile card below so the two
  // layouts can never drift apart on what a shop can do with an order.
  function statusCell(o: DashboardOrder) {
    const meta = statusMeta(o.status);
    return (
      <>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${meta.className}`}>
                          {meta.label}
                        </span>
                        {o.payment_status && o.status !== "cancelled" && (
                          <p
                            className={`text-[11px] mt-1 ${
                              o.payment_status === "paid"
                                ? "text-emerald-600"
                                : o.payment_status === "submitted"
                                  ? "text-amber-600"
                                  : "text-gray-500"
                            }`}
                          >
                            {o.payment_status === "paid"
                              ? `Paid (${o.payment_method === "cash" ? "cash" : "UPI"})`
                              : o.payment_status === "submitted"
                                ? `UPI paid? ref ${o.payer_reference || "—"}`
                                : o.payment_method === "cash"
                                  ? `Collect ${formatINR(o.total_amount)} cash`
                                  : "Awaiting UPI payment"}
                          </p>
                        )}
                        {o.delivery_proof_photo_url && (
                          <a
                            href={o.delivery_proof_photo_url}
                            target="_blank"
                            rel="noreferrer"
                            className="block text-[11px] text-blue-500 underline mt-1"
                          >
                            View proof photo
                          </a>
                        )}
      </>
    );
  }

  function actionCell(o: DashboardOrder) {
    const action = transitionsForFulfillment(o.fulfillment_type)[o.status];
    return (
                        <div className="flex flex-col items-start gap-1.5">
                          {canManagePayments && o.payment_status === "submitted" && (
                            <div className="flex gap-1.5">
                              <button
                                onClick={() => orderAction(o, "/payment/confirm")}
                                disabled={updatingId === o.id}
                                className="bg-emerald-600 text-white text-xs font-medium rounded-md px-3 py-1.5 disabled:opacity-50"
                              >
                                Payment received
                              </button>
                              <button
                                onClick={() =>
                                  orderAction(o, "/payment/reject", "Mark this payment as NOT received?")
                                }
                                disabled={updatingId === o.id}
                                className="text-xs text-red-500 px-2 disabled:opacity-50"
                              >
                                Not received
                              </button>
                            </div>
                          )}
                          {canManagePayments && o.payment_status === "unpaid" && o.payment_method === "upi" && o.status !== "cancelled" && (
                            <button
                              onClick={() => orderAction(o, "/payment/confirm", "Mark this order as paid?")}
                              disabled={updatingId === o.id}
                              className="text-xs text-emerald-700 hover:underline disabled:opacity-50"
                            >
                              Mark as paid
                            </button>
                          )}
                          {action && (
                            <button
                              onClick={() => accept(o)}
                              disabled={updatingId === o.id}
                              className="bg-blue-600 text-white text-xs font-medium rounded-md px-3 py-1.5 disabled:opacity-50"
                            >
                              {updatingId === o.id ? "…" : action.label}
                            </button>
                          )}
                          {canManagePayments && SHOP_CANCELABLE.has(o.status) && (
                            <button
                              onClick={() =>
                                orderAction(o, "/cancel", "Cancel this order? Stock will be released. If the customer already paid, you'll need to refund them yourself.")
                              }
                              disabled={updatingId === o.id}
                              className="text-xs text-red-500 hover:underline disabled:opacity-50"
                            >
                              Cancel order
                            </button>
                          )}
                          {!action && !SHOP_CANCELABLE.has(o.status) && o.payment_status !== "submitted" && (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-4">
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
          <>
          {/* Phones: one card per order (a 7-column table is unusable there). */}
          <div className="md:hidden divide-y divide-gray-100">
            {filtered.map((o) => (
              <div key={o.id} className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-blue-600 font-medium text-sm">#{o.id.slice(0, 8)}</p>
                    <p className="text-sm text-gray-800 truncate">{o.buyer_name || "—"}</p>
                    <p className="text-xs text-gray-400 truncate">{o.buyer_email}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-semibold text-gray-900">{formatINR(o.total_amount)}</p>
                    <p className="text-xs text-gray-400">
                      {o.item_count} items · {timeAgo(o.created_at)}
                    </p>
                    <span
                      className={`inline-block mt-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${
                        o.fulfillment_type === "pickup" ? "bg-teal-50 text-teal-700" : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {o.fulfillment_type === "pickup" ? "Pickup" : "Delivery"}
                    </span>
                  </div>
                </div>
                <div>{statusCell(o)}</div>
                {actionCell(o)}
              </div>
            ))}
          </div>

          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50/50">
                  <th className="px-5 py-3 font-medium">Order ID</th>
                  <th className="px-5 py-3 font-medium">Customer</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">Items</th>
                  <th className="px-5 py-3 font-medium">Total</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Time</th>
                  <th className="px-5 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((o) => {
                  return (
                    <tr key={o.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/40">
                      <td className="px-5 py-3 text-blue-600 font-medium">#{o.id.slice(0, 8)}</td>
                      <td className="px-5 py-3">
                        <p className="text-gray-800">{o.buyer_name || "—"}</p>
                        <p className="text-xs text-gray-400">{o.buyer_email}</p>
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            o.fulfillment_type === "pickup"
                              ? "bg-teal-50 text-teal-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {o.fulfillment_type === "pickup" ? "Pickup" : "Delivery"}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-gray-500">{o.item_count} items</td>
                      <td className="px-5 py-3 font-medium text-gray-800">{formatINR(o.total_amount)}</td>
                      <td className="px-5 py-3">
                        {statusCell(o)}
                      </td>
                      <td className="px-5 py-3 text-gray-400">{timeAgo(o.created_at)}</td>
                      <td className="px-5 py-3">
                        {actionCell(o)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>

      {proofOrder && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm space-y-4">
            <div>
              <h3 className="font-semibold text-gray-900">Confirm delivery</h3>
              <p className="text-sm text-gray-500 mt-1">
                Take or upload a photo of the order at the doorstep as proof of delivery for order #
                {proofOrder.id.slice(0, 8)}.
              </p>
            </div>

            {proofPreview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={proofPreview} alt="Delivery proof preview" className="w-full h-48 object-cover rounded-lg" />
            ) : (
              <div className="h-48 border-2 border-dashed border-gray-200 rounded-lg flex flex-col items-center justify-center gap-3 p-3">
                <div className="flex gap-2 w-full">
                  <label className="flex-1 text-center bg-blue-600 text-white text-sm font-medium rounded-lg px-3 py-2.5 cursor-pointer">
                    Take photo
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      className="hidden"
                      onChange={(e) => { pickProofFile(e.target.files?.[0] ?? null); e.target.value = ""; }}
                    />
                  </label>
                  <label className="flex-1 text-center border border-gray-300 text-gray-700 text-sm font-medium rounded-lg px-3 py-2.5 cursor-pointer">
                    From gallery
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => { pickProofFile(e.target.files?.[0] ?? null); e.target.value = ""; }}
                    />
                  </label>
                </div>
                <span className="text-xs text-gray-400">Any photo size is fine — it&apos;s shrunk automatically</span>
              </div>
            )}

            {proofPreview && (
              <button
                onClick={() => pickProofFile(null)}
                className="text-xs font-medium text-gray-500 underline"
              >
                Choose a different photo
              </button>
            )}

            {proofError && <p className="text-sm text-red-500">{proofError}</p>}

            <div className="flex gap-2 justify-end">
              <button
                onClick={closeProofModal}
                disabled={submittingProof}
                className="text-sm font-medium text-gray-600 px-4 py-2 rounded-lg disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={submitProof}
                disabled={!proofFile || submittingProof}
                className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-50"
              >
                {submittingProof ? "Marking delivered…" : "Mark Delivered"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
