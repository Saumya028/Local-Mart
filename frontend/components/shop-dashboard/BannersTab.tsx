"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { uploadProductImage } from "@/lib/imageUpload";
import { loadRazorpay } from "@/lib/razorpay";

type Slot = {
  key: string;
  name: string;
  description: string;
  width: number;
  height: number;
  price: string;
  duration_days: number;
};
type SlotsResponse = { mode: "razorpay" | "test" | null; razorpay_key_id: string | null; slots: Slot[] };
type State = "pending" | "rejected" | "awaiting_payment" | "live" | "expired";
type MyBanner = {
  id: string;
  slot_key: string;
  slot_name: string;
  width: number;
  height: number;
  price: string;
  duration_days: number;
  image_url: string;
  title: string | null;
  state: State;
  rejection_reason: string | null;
  ends_at: string | null;
  impressions: number;
  clicks: number;
};
type Checkout = {
  payment_id: string;
  mode: "razorpay" | "test";
  razorpay_key_id: string | null;
  razorpay_order_id: string | null;
  amount_paise: number | null;
};

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";
const inr = (v: string | number) => `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const daysLeft = (iso: string | null) => (iso ? Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000) : 0);

const STATE_META: Record<State, { label: string; cls: string }> = {
  pending: { label: "In review", cls: "bg-gray-100 text-gray-600" },
  rejected: { label: "Rejected", cls: "bg-red-50 text-red-600" },
  awaiting_payment: { label: "Approved — pay to go live", cls: "bg-amber-50 text-amber-700" },
  live: { label: "Live", cls: "bg-emerald-50 text-emerald-600" },
  expired: { label: "Ended", cls: "bg-gray-100 text-gray-500" },
};

// Where a shop owner buys banner space. Flow: request a spot + upload the
// artwork -> admin reviews it -> once approved, pay -> it runs for the
// spot's duration for customers near the shop -> renew when it ends.
export function BannersTab({ shopId, userId, approved }: { shopId: string; userId: string; approved: boolean }) {
  const [slots, setSlots] = useState<SlotsResponse | null>(null);
  const [banners, setBanners] = useState<MyBanner[]>([]);
  const [slotKey, setSlotKey] = useState("");
  const [title, setTitle] = useState("");
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, b] = await Promise.all([apiFetch("/banners/slots"), apiFetch(`/banners/shops/${shopId}`)]);
      setSlots(s);
      setBanners(b);
      setSlotKey((k) => k || s.slots[0]?.key || "");
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [shopId]);

  useEffect(() => {
    load();
  }, [load]);

  const slot = slots?.slots.find((s) => s.key === slotKey) ?? null;

  async function onFile(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      setImageUrl(await uploadProductImage(userId, file));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function submit() {
    if (!slot || !imageUrl) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await apiFetch(`/banners/shops/${shopId}`, {
        method: "POST",
        body: JSON.stringify({ slot_key: slot.key, image_url: imageUrl, title: title.trim() || null }),
      });
      setImageUrl(null);
      setTitle("");
      setNotice("Request sent. You'll be able to pay once it's approved — check back on this page.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function withdraw(b: MyBanner) {
    if (!window.confirm("Remove this banner request?")) return;
    setBusyId(b.id);
    try {
      await apiFetch(`/banners/${b.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  async function confirm(b: MyBanner, body: Record<string, unknown>) {
    await apiFetch(`/banners/${b.id}/confirm`, { method: "POST", body: JSON.stringify(body) });
    setNotice(`Payment received — your banner is live for ${b.duration_days} days.`);
    await load();
  }

  async function pay(b: MyBanner) {
    setBusyId(b.id);
    setError(null);
    setNotice(null);
    try {
      const co: Checkout = await apiFetch(`/banners/${b.id}/checkout`, { method: "POST" });
      if (co.mode === "test") {
        // Local development only — the server refuses this in production.
        await confirm(b, { payment_id: co.payment_id });
        setBusyId(null);
        return;
      }
      if (!(await loadRazorpay()) || !window.Razorpay) {
        throw new Error("Couldn't load the payment window. Check your connection and try again.");
      }
      const rzp = new window.Razorpay({
        key: co.razorpay_key_id,
        order_id: co.razorpay_order_id,
        amount: co.amount_paise,
        currency: "INR",
        name: "LocalMart",
        description: `Banner — ${b.slot_name}`,
        handler: async (resp: { razorpay_payment_id: string; razorpay_signature: string }) => {
          try {
            await confirm(b, {
              payment_id: co.payment_id,
              razorpay_payment_id: resp.razorpay_payment_id,
              razorpay_signature: resp.razorpay_signature,
            });
          } catch (err) {
            setError(
              `Payment received but activation hasn't completed yet (${(err as Error).message}). It will activate automatically within a minute — refresh this page.`
            );
          } finally {
            setBusyId(null);
          }
        },
        modal: { ondismiss: () => setBusyId(null) },
      });
      rzp.open();
    } catch (err) {
      setError((err as Error).message);
      setBusyId(null);
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-4xl space-y-5">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 sm:p-6">
        <h3 className="font-semibold text-gray-900">Advertise with a banner</h3>
        <p className="text-sm text-gray-500 mt-1">
          Pick a spot, upload your artwork and we&apos;ll review it. Once approved, pay to put it live. Customers
          close to your shop see it, and tapping it opens your shop page. Each booking runs for a fixed period —
          renew when it ends.
        </p>
        {slots?.mode === "test" && (
          <p className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            Test mode — no real payment is taken.
          </p>
        )}
      </div>

      {error && <p className="text-sm text-red-500 break-words">{error}</p>}
      {notice && (
        <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">{notice}</p>
      )}

      {!approved ? (
        <p className="text-sm text-gray-500">You can request banners once your shop has been approved.</p>
      ) : !slots ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-100 p-5 sm:p-6 space-y-4">
          <h4 className="font-medium text-gray-900 text-sm">New banner request</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {slots.slots.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setSlotKey(s.key)}
                className={`text-left rounded-xl border p-3 transition ${
                  slotKey === s.key ? "border-blue-500 bg-blue-50/40" : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <p className="text-sm font-medium text-gray-900">{s.name}</p>
                <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {s.width}×{s.height}px · {s.duration_days} days ·{" "}
                  <span className="font-semibold text-gray-700">{inr(s.price)}</span>
                </p>
              </button>
            ))}
          </div>

          {slot && (
            <div className="space-y-3">
              <div
                className="relative w-full max-w-xl overflow-hidden rounded-xl border border-dashed border-gray-300 bg-gray-50 flex items-center justify-center text-xs text-gray-400"
                style={{ aspectRatio: `${slot.width} / ${slot.height}` }}
              >
                {imageUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element -- just-uploaded Supabase Storage URL
                  <img src={imageUrl} alt="" className="absolute inset-0 w-full h-full object-cover" />
                ) : (
                  <span>
                    Preview — use a {slot.width}×{slot.height} image (the frame crops to fit)
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-sm font-medium text-blue-600 border border-blue-200 rounded-lg px-3 py-2 cursor-pointer hover:bg-blue-50">
                  {uploading ? "Uploading…" : imageUrl ? "Change image" : "Upload image"}
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    disabled={uploading}
                    onChange={(e) => onFile(e.target.files?.[0])}
                  />
                </label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={120}
                  placeholder="Short caption (optional)"
                  className="flex-1 min-w-[200px] border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={submit}
                  disabled={!imageUrl || submitting}
                  className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-50"
                >
                  {submitting ? "Sending…" : "Send for review"}
                </button>
              </div>
              <p className="text-xs text-gray-400">
                You pay {inr(slot.price)} for {slot.duration_days} days only after we approve the artwork.
              </p>
            </div>
          )}
        </div>
      )}

      {banners.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-gray-900 text-sm">Your banners</h4>
          {banners.map((b) => {
            const meta = STATE_META[b.state];
            const canRenew = b.state === "expired" || (b.state === "live" && daysLeft(b.ends_at) <= 7);
            return (
              <div key={b.id} className="bg-white rounded-2xl border border-gray-100 p-4 flex flex-col sm:flex-row gap-4">
                <div
                  className="relative w-full sm:w-64 shrink-0 overflow-hidden rounded-lg bg-gray-50"
                  style={{ aspectRatio: `${b.width} / ${b.height}` }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element -- advertiser-uploaded Supabase Storage URL */}
                  <img src={b.image_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
                </div>
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-gray-900">{b.slot_name}</p>
                    <span className={`text-xs font-medium rounded-full px-2.5 py-1 ${meta.cls}`}>{meta.label}</span>
                  </div>
                  {b.title && <p className="text-xs text-gray-500">&ldquo;{b.title}&rdquo;</p>}
                  {b.state === "rejected" && b.rejection_reason && (
                    <p className="text-xs text-red-500">Reason: {b.rejection_reason}</p>
                  )}
                  {(b.state === "live" || b.state === "expired") && (
                    <p className="text-xs text-gray-500">
                      {b.state === "live" ? `Runs until ${fmtDate(b.ends_at)}` : `Ended ${fmtDate(b.ends_at)}`} ·{" "}
                      {b.impressions.toLocaleString("en-IN")} views · {b.clicks.toLocaleString("en-IN")} clicks
                    </p>
                  )}
                  <div className="flex flex-wrap gap-3 pt-1">
                    {b.state === "awaiting_payment" && (
                      <button
                        onClick={() => pay(b)}
                        disabled={busyId === b.id}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg px-3 py-1.5 disabled:opacity-50"
                      >
                        {busyId === b.id ? "Processing…" : `Pay ${inr(b.price)} · ${b.duration_days} days`}
                      </button>
                    )}
                    {canRenew && (
                      <button
                        onClick={() => pay(b)}
                        disabled={busyId === b.id}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg px-3 py-1.5 disabled:opacity-50"
                      >
                        {busyId === b.id ? "Processing…" : `Renew ${inr(b.price)} · ${b.duration_days} days`}
                      </button>
                    )}
                    {b.state !== "live" && (
                      <button
                        onClick={() => withdraw(b)}
                        disabled={busyId === b.id}
                        className="text-xs text-gray-500 hover:underline disabled:opacity-50"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
