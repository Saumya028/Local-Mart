"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { isValidUpiId } from "@/lib/upi";
import { uploadProductImage } from "@/lib/imageUpload";
import { Shop } from "./types";

// Where a shop owner tells customers how to pay them. Payment goes
// straight from the customer to the shop (UPI or cash) — LocalMart never
// holds the money, so these details are all a customer needs.
export function PaymentSettingsTab({
  shop,
  userId,
  onSaved,
}: {
  shop: Shop;
  userId: string;
  onSaved: (updated: Shop) => void;
}) {
  const [upiId, setUpiId] = useState(shop.upi_id ?? "");
  const [qrUrl, setQrUrl] = useState(shop.upi_qr_url ?? "");
  const [acceptsUpi, setAcceptsUpi] = useState(shop.accepts_upi);
  const [acceptsCash, setAcceptsCash] = useState(shop.accepts_cash);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function onQrFile(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      setQrUrl(await uploadProductImage(userId, file));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function save() {
    setError(null);
    setSaved(false);
    const trimmed = upiId.trim();
    if (trimmed && !isValidUpiId(trimmed)) {
      setError("Enter a valid UPI ID, like shopname@okaxis.");
      return;
    }
    if (acceptsUpi && !trimmed && !qrUrl) {
      setError("Add a UPI ID or upload your QR code to accept UPI, or switch UPI off.");
      return;
    }
    if (!acceptsUpi && !acceptsCash) {
      setError("Turn on at least one way to get paid — customers couldn't order otherwise.");
      return;
    }
    setSaving(true);
    try {
      const updated: Shop = await apiFetch(`/dashboard/shops/${shop.id}`, {
        method: "PUT",
        body: JSON.stringify({
          upi_id: trimmed,
          upi_qr_url: qrUrl,
          accepts_upi: acceptsUpi,
          accepts_cash: acceptsCash,
        }),
      });
      onSaved(updated);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <p className="text-sm text-gray-500">
        Customers pay you directly — by UPI or cash. LocalMart never touches the money, so there are no payment
        fees, and you confirm each payment yourself from the Orders tab.
      </p>

      <section className="bg-white border border-gray-100 rounded-2xl p-5 space-y-4">
        <label className="flex items-center justify-between">
          <span className="font-semibold text-gray-900">Accept UPI</span>
          <input type="checkbox" checked={acceptsUpi} onChange={(e) => setAcceptsUpi(e.target.checked)} />
        </label>

        <div className="space-y-1">
          <label className="text-sm text-gray-600">UPI ID</label>
          <input
            value={upiId}
            onChange={(e) => setUpiId(e.target.value)}
            placeholder="shopname@okaxis"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-400">
            Lets customers tap &ldquo;Pay with UPI app&rdquo; with the amount already filled in. Some apps block
            this for personal accounts — your QR below is the fallback.
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-sm text-gray-600">Your UPI QR code (optional)</label>
          {qrUrl && (
            <div className="flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={qrUrl} alt="Your UPI QR" className="w-32 h-32 object-contain border rounded-lg bg-white" />
              <button type="button" onClick={() => setQrUrl("")} className="text-xs text-red-500">
                Remove
              </button>
            </div>
          )}
          <input
            type="file"
            accept="image/*"
            disabled={uploading}
            onChange={(e) => onQrFile(e.target.files?.[0])}
            className="text-sm"
          />
          {uploading && <p className="text-xs text-gray-400">Uploading…</p>}
          <p className="text-xs text-gray-400">
            Screenshot or download the QR from your UPI app (GPay / PhonePe / Paytm → your QR code) and upload it.
            Without one, we generate a QR from your UPI ID.
          </p>
        </div>
      </section>

      <section className="bg-white border border-gray-100 rounded-2xl p-5">
        <label className="flex items-center justify-between">
          <span>
            <span className="font-semibold text-gray-900 block">Accept cash</span>
            <span className="text-xs text-gray-400">Cash on delivery, or cash when the customer picks up.</span>
          </span>
          <input type="checkbox" checked={acceptsCash} onChange={(e) => setAcceptsCash(e.target.checked)} />
        </label>
      </section>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {saved && <p className="text-sm text-emerald-600">Saved.</p>}

      <button
        onClick={save}
        disabled={saving || uploading}
        className="bg-blue-600 text-white rounded-lg px-5 py-2 text-sm font-medium disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save payment settings"}
      </button>
    </div>
  );
}
