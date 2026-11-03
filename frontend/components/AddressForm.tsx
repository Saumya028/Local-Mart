"use client";

import { KeyboardEvent, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { AddressValues, EMPTY_ADDRESS, validateAddress } from "@/lib/customerFields";
import { AddressFields } from "@/components/customer/FormParts";
import { getCurrentPosition } from "@/lib/useViewerLocation";

export default function AddressForm({
  onSaved,
  onCancel,
}: {
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const [address, setAddress] = useState<AddressValues>(EMPTY_ADDRESS);
  const [isDefault, setIsDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Map pin — captured with the browser's location. Decides which shops can
  // deliver to this address (each shop has its own delivery radius).
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null);
  const [pinning, setPinning] = useState(false);

  async function pinHere() {
    setPinning(true);
    setError(null);
    try {
      setPin(await getCurrentPosition());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPinning(false);
    }
  }

  async function handleSubmit() {
    const problem = validateAddress(address);
    if (problem) {
      setError(problem);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/addresses", {
        method: "POST",
        body: JSON.stringify({
          ...address,
          line2: address.line2.trim() || null,
          landmark: address.landmark.trim() || null,
          is_default: isDefault,
          lat: pin?.lat ?? null,
          lng: pin?.lng ?? null,
        }),
      });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  // Deliberately a <div>, not a <form>: this component is rendered inside
  // the checkout page's own <form>, and HTML forbids nested forms (it
  // causes a hydration error). So Enter is handled by hand — it saves the
  // address instead of submitting the surrounding checkout form.
  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT") {
      e.preventDefault();
      if (!saving) handleSubmit();
    }
  }

  return (
    <div onKeyDown={handleKeyDown} className="space-y-3 border rounded-lg p-4">
      <AddressFields
        required={false}
        value={address}
        onChange={(patch) => setAddress((a) => ({ ...a, ...patch }))}
      />

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button
          type="button"
          onClick={pinHere}
          disabled={pinning}
          className="text-blue-600 border border-blue-200 rounded-full px-3 py-1.5 hover:bg-blue-50 disabled:opacity-50"
        >
          {pinning ? "Locating…" : pin ? "📍 Update pin" : "📍 Use my current location"}
        </button>
        <span className={pin ? "text-emerald-700 text-xs" : "text-gray-500 text-xs"}>
          {pin
            ? "Location pinned — stand at this address when you tap the button."
            : "Tap this while you are at this address so we can show shops that deliver here."}
        </span>
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-600">
        <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
        Set as default
      </label>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={saving}
          className="bg-blue-600 text-white rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save address"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="text-sm text-gray-500 underline">
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
