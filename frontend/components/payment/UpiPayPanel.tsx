"use client";

import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { isValidPayerReference } from "@/lib/upi";

type Props = {
  amount: string;
  payeeName: string | null;
  upiId: string | null;
  upiQrUrl: string | null;
  upiLink: string | null;
  // "unpaid" = customer hasn't said they paid, "submitted" = waiting on
  // the shop to confirm, "paid" = shop confirmed.
  status: string;
  payerReference?: string | null;
  busy?: boolean;
  onMarkPaid: (payerReference: string) => void | Promise<void>;
};

// Shown to the customer wherever they need to pay a shop by UPI: the
// order page, and an exchange's price-difference top-up. The money goes
// straight to the shop — this only helps them send it and tell us they did.
export default function UpiPayPanel({
  amount,
  payeeName,
  upiId,
  upiQrUrl,
  upiLink,
  status,
  payerReference,
  busy = false,
  onMarkPaid,
}: Props) {
  const [ref, setRef] = useState("");
  const [copied, setCopied] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  if (status === "paid") {
    return (
      <div className="rounded-xl bg-emerald-50 text-emerald-700 text-sm px-4 py-3">
        ₹{amount} paid to {payeeName ?? "the shop"} — confirmed.
      </div>
    );
  }

  if (status === "submitted") {
    return (
      <div className="rounded-xl bg-amber-50 text-amber-700 text-sm px-4 py-3 space-y-1">
        <p className="font-medium">Waiting for {payeeName ?? "the shop"} to confirm your payment of ₹{amount}.</p>
        {payerReference && <p className="text-xs">Reference you gave: {payerReference}</p>}
        <p className="text-xs">If it doesn&apos;t get confirmed, contact the shop and show them your UPI receipt.</p>
      </div>
    );
  }

  async function copyUpiId() {
    if (!upiId) return;
    try {
      await navigator.clipboard.writeText(upiId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked; the id is visible on screen anyway.
    }
  }

  function submit() {
    const value = ref.trim();
    if (value && !isValidPayerReference(value)) {
      setLocalError("The transaction/UTR number should be 8-30 letters or digits.");
      return;
    }
    setLocalError(null);
    onMarkPaid(value);
  }

  return (
    <div className="rounded-xl border border-gray-200 p-4 space-y-4">
      <div>
        <p className="font-semibold text-gray-900">Pay ₹{amount} to {payeeName ?? "the shop"} by UPI</p>
        <p className="text-xs text-gray-500">
          The money goes straight to the shop — LocalMart never handles it.
        </p>
      </div>

      {upiLink && (
        <a
          href={upiLink}
          className="block text-center bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium"
        >
          Pay with UPI app
        </a>
      )}

      <div className="flex flex-col items-center gap-2">
        {upiQrUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={upiQrUrl} alt={`${payeeName ?? "Shop"} UPI QR code`} className="w-48 h-48 object-contain border rounded-lg bg-white" />
        ) : upiLink ? (
          <div className="p-2 bg-white border rounded-lg">
            <QRCodeSVG value={upiLink} size={176} />
          </div>
        ) : null}
        <p className="text-xs text-gray-400">Scan with any UPI app{upiQrUrl ? " — and enter ₹" + amount : ""}</p>
      </div>

      {upiId && (
        <div className="flex items-center justify-between gap-2 bg-gray-50 rounded-lg px-3 py-2 text-sm">
          <span className="truncate">
            UPI ID: <span className="font-mono">{upiId}</span>
          </span>
          <button type="button" onClick={copyUpiId} className="text-xs text-blue-600 shrink-0">
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      )}

      <div className="space-y-2 pt-1 border-t">
        <p className="text-sm text-gray-700 pt-3">After paying:</p>
        <input
          value={ref}
          onChange={(e) => setRef(e.target.value)}
          placeholder="UTR / transaction number (optional)"
          className="w-full border rounded-lg px-3 py-2 text-sm"
        />
        {localError && <p className="text-xs text-red-500">{localError}</p>}
        <button
          type="button"
          onClick={submit}
          disabled={busy}
          className="w-full bg-emerald-600 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50"
        >
          {busy ? "Sending…" : "I've paid"}
        </button>
      </div>
    </div>
  );
}
