"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { AccountProfile } from "./types";

export function SettingsTab({ profile, onUpdated }: { profile: AccountProfile; onUpdated: (p: AccountProfile) => void }) {
  const [fullName, setFullName] = useState(profile.full_name ?? "");
  const [phone, setPhone] = useState(profile.phone ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated: AccountProfile = await apiFetch("/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ full_name: fullName || null, phone: phone || null }),
      });
      onUpdated(updated);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 max-w-md">
      <h2 className="font-semibold text-gray-900 mb-4">Account Settings</h2>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Full name</label>
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Phone number</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+91 98765 43210"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Email</label>
          <input
            value={profile.email ?? "No email on file (signed in by phone)"}
            disabled
            className="w-full border border-gray-100 bg-gray-50 rounded-lg px-3 py-2 text-sm text-gray-400"
          />
          <p className="text-xs text-gray-400 mt-1">Managed by your login provider — not editable here.</p>
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}
        {saved && !error && <p className="text-sm text-emerald-600">Saved.</p>}

        <button
          type="submit"
          disabled={saving}
          className="bg-blue-600 text-white rounded-lg px-5 py-2 text-sm font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      </form>
    </div>
  );
}
