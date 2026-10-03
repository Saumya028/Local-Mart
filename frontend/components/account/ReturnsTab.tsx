"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/apiClient";
import UpiPayPanel from "@/components/payment/UpiPayPanel";
import { ReturnRequest, returnStatusMeta } from "./types";

type DifferenceInfo = {
  amount: string;
  method: string | null;
  payee_name: string | null;
  upi_id: string | null;
  upi_qr_url: string | null;
  upi_link: string | null;
  shop_accepts_upi: boolean;
  shop_accepts_cash: boolean;
};

export function ReturnsTab() {
  const [returns, setReturns] = useState<ReturnRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [payingId, setPayingId] = useState<string | null>(null);
  // Which return's pay-the-difference panel is open, and what the
  // backend says about where to send the money.
  const [openPayId, setOpenPayId] = useState<string | null>(null);
  const [diffInfo, setDiffInfo] = useState<DifferenceInfo | null>(null);

  async function load() {
    try {
      const data = await apiFetch("/returns");
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
  }, []);

  async function cancel(id: string) {
    setCancellingId(id);
    try {
      await apiFetch(`/returns/${id}/cancel`, { method: "POST" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCancellingId(null);
    }
  }

  // Opens the pay-the-shop panel for an exchange's price-difference
  // top-up. Payment goes straight to the shop (UPI or cash); the shop
  // confirms receipt, which is what lets them complete the exchange.
  async function openDifference(r: ReturnRequest) {
    setError(null);
    try {
      const info: DifferenceInfo = await apiFetch(`/returns/${r.id}/difference-payment`);
      setDiffInfo(info);
      setOpenPayId(r.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function chooseMethod(r: ReturnRequest, method: "upi" | "cash", payerReference?: string) {
    setPayingId(r.id);
    setError(null);
    try {
      const info: DifferenceInfo = await apiFetch(`/returns/${r.id}/difference-payment`, {
        method: "POST",
        body: JSON.stringify({ method, payer_reference: payerReference || null }),
      });
      setDiffInfo(info);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPayingId(null);
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading returns…</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;

  if (returns.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
        <p className="text-sm text-gray-500">You haven&apos;t requested any returns or exchanges yet.</p>
        <p className="text-xs text-gray-400 mt-1">
          Open a delivered order from My Orders to start one within the return window.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {returns.map((r) => {
        const meta = returnStatusMeta(r.status);
        return (
          <div key={r.id} className="bg-white rounded-2xl border border-gray-100 p-5 space-y-2">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-gray-900">{r.product_name ?? "Item"}</p>
                <p className="text-xs text-gray-400">
                  {r.shop_name ?? "Shop"} · {r.request_type === "exchange" ? "Exchange" : "Return"} ·{" "}
                  {r.quantity} unit(s)
                </p>
              </div>
              <span className={`text-xs font-medium rounded-full px-2.5 py-1 whitespace-nowrap ${meta.className}`}>
                {meta.label}
              </span>
            </div>

            <p className="text-sm text-gray-600">Reason: {r.reason}</p>
            {r.request_type === "exchange" && r.exchange_product_name && (
              <p className="text-sm text-gray-600">Replacement: {r.exchange_product_name}</p>
            )}
            {r.request_type === "return" && (
              <p className="text-sm text-gray-600">Refund amount: ₹{r.refund_amount}</p>
            )}

            {/* Exchange price difference — only ever non-zero for an
                exchange. Positive means the customer owes the gap and,
                once the shop approves, needs to pay it before the shop
                can complete the swap; negative means the shop owes a
                partial refund back, settled the same offline way a
                plain return's refund_amount is. */}
            {r.request_type === "exchange" && parseFloat(r.price_difference) > 0.004 && (
              <div className="rounded-lg px-3 py-2 bg-amber-50 text-amber-700 text-sm flex items-center justify-between gap-3">
                <span>
                  {r.difference_paid
                    ? `Price difference of ₹${r.price_difference} received by the shop.`
                    : `This exchange costs ₹${r.price_difference} more.`}
                </span>
                {!r.difference_paid && r.status === "approved" && openPayId !== r.id && (
                  <button
                    onClick={() => openDifference(r)}
                    className="shrink-0 text-xs font-medium bg-amber-600 text-white rounded-lg px-3 py-1.5"
                  >
                    {r.difference_method ? "Payment details" : `Pay ₹${r.price_difference}`}
                  </button>
                )}
              </div>
            )}

            {openPayId === r.id && diffInfo && !r.difference_paid && (
              <div className="space-y-3">
                <div className="flex gap-4 text-sm">
                  {diffInfo.shop_accepts_upi && (
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        checked={diffInfo.method === "upi"}
                        onChange={() => chooseMethod(r, "upi")}
                        disabled={payingId === r.id}
                      />
                      UPI
                    </label>
                  )}
                  {diffInfo.shop_accepts_cash && (
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        checked={diffInfo.method === "cash"}
                        onChange={() => chooseMethod(r, "cash")}
                        disabled={payingId === r.id}
                      />
                      Cash (pay the shop in person)
                    </label>
                  )}
                </div>
                {diffInfo.method === "upi" && (
                  <UpiPayPanel
                    amount={diffInfo.amount}
                    payeeName={diffInfo.payee_name}
                    upiId={diffInfo.upi_id}
                    upiQrUrl={diffInfo.upi_qr_url}
                    upiLink={diffInfo.upi_link}
                    status={r.difference_payer_reference ? "submitted" : "unpaid"}
                    payerReference={r.difference_payer_reference}
                    busy={payingId === r.id}
                    onMarkPaid={(ref) => chooseMethod(r, "upi", ref)}
                  />
                )}
                {diffInfo.method === "cash" && (
                  <p className="text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
                    Hand ₹{diffInfo.amount} to {diffInfo.payee_name ?? "the shop"} — they&apos;ll mark it received
                    and complete your exchange.
                  </p>
                )}
              </div>
            )}
            {r.request_type === "exchange" && parseFloat(r.price_difference) < -0.004 && (
              <p className="rounded-lg px-3 py-2 bg-emerald-50 text-emerald-700 text-sm">
                The shop owes you a refund of ₹{Math.abs(parseFloat(r.price_difference)).toFixed(2)}{" "}
                for the cheaper replacement, settled once this is completed.
              </p>
            )}

            {r.shop_note && (
              <p className="text-sm text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
                Shop note: {r.shop_note}
              </p>
            )}

            <div className="flex items-center gap-4 pt-1">
              <Link href={`/orders/${r.order_id}`} className="text-xs text-blue-600 hover:underline">
                View order
              </Link>
              {r.new_order_id && (
                <Link
                  href={`/orders/${r.new_order_id}`}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Track replacement order
                </Link>
              )}
              {r.status === "requested" && (
                <button
                  onClick={() => cancel(r.id)}
                  disabled={cancellingId === r.id}
                  className="text-xs text-red-500 hover:underline disabled:opacity-50"
                >
                  {cancellingId === r.id ? "Cancelling…" : "Cancel request"}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
