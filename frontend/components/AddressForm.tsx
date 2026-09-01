"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/apiClient";

export default function AddressForm({
  onSaved,
  onCancel,
}: {
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const [label, setLabel] = useState("Home");
  const [line1, setLine1] = useState("");
  const [city, setCity] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/addresses", {
        method: "POST",
        body: JSON.stringify({ label, line1, city, is_default: isDefault }),
      });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border rounded-lg p-4">
      <div className="grid grid-cols-2 gap-3">
        <input
          placeholder="Label (e.g. Home)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          placeholder="City"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <input
        placeholder="Address line"
        value={line1}
        onChange={(e) => setLine1(e.target.value)}
        required
        className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      <label className="flex items-center gap-2 text-sm text-gray-600">
        <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
        Set as default
      </label>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex gap-3">
        <button
          type="submit"
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
    </form>
  );
}
