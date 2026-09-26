"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/apiClient";
import { ReturnRequest, returnStatusMeta } from "./types";

// Same loader as app/checkout/page.tsx — duplicated rather than shared,
// since it's a dozen lines and pulling it into a common module isn't
// worth the churn for this one extra call site. `window.Razorpay` is
// global once loaded either way, so calling this here after checkout
// already loaded it on some earlier page view is just an instant no-op.
let razorpayScriptPromise: Promise<void> | null = null;
function loadRazorpayScript(): Promise<void> {
  if (typeof window !== "undefined" && (window as any).Razorpay) {
    return Promise.resolve();
  }
  if (!razorpayScriptPromise) {
    razorpayScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load Razorpay checkout"));
      document.body.appendChild(script);
    });
  }
  return razorpayScriptPromise;
}

export function ReturnsTab() {
  const [returns, setReturns] = useState<ReturnRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [payingId, setPayingId] = useState<string | null>(null);

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

  // Opens Razorpay's popup for the exchange's price-difference top-up —
  // the same POST-then-verify pattern as checkout/page.tsx's
  // openRazorpayCheckout, just against
  // /returns/{id}/difference-payment + /verify-difference-payment
  // instead of the main /orders + /orders/verify-payment pair.
  async function payDifference(r: ReturnRequest) {
    setPayingId(r.id);
    setError(null);
    try {
      const data = await apiFetch(`/returns/${r.id}/difference-payment`, { method: "POST" });
      await loadRazorpayScript();
      const razorpay = new (window as any).Razorpay({
        key: data.razorpay_key_id,
        order_id: data.razorpay_order_id,
        amount: Math.round(parseFloat(data.amount) * 100),
        currency: "INR",
        name: "LocalMart",
        description: `Price difference for exchanging ${r.product_name ?? "an item"}`,
        handler: async function (response: {
          razorpay_order_id: string;
          razorpay_payment_id: string;
          razorpay_signature: string;
        }) {
          try {
            await apiFetch(`/returns/${r.id}/verify-difference-payment`, {
              method: "POST",
              body: JSON.stringify({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              }),
            });
          } catch {
            // Same reasoning as checkout: a verification network blip
            // right after a real payment isn't a sign the payment
            // failed, so this stays reassuring rather than alarming.
          } finally {
            await load();
          }
        },
        modal: {
          ondismiss: function () {
            setPayingId(null);
          },
        },
        theme: { color: "#2563eb" },
      });
      razorpay.open();
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
                    ? `Price difference of ₹${r.price_difference} paid — waiting on the shop.`
                    : `This exchange costs ₹${r.price_difference} more.`}
                </span>
                {!r.difference_paid && r.status === "approved" && (
                  <button
                    onClick={() => payDifference(r)}
                    disabled={payingId === r.id}
                    className="shrink-0 text-xs font-medium bg-amber-600 text-white rounded-lg px-3 py-1.5 disabled:opacity-50"
                  >
                    {payingId === r.id ? "Opening…" : `Pay ₹${r.price_difference}`}
                  </button>
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
