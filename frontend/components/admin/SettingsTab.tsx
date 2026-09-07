"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { PlatformSettings } from "./types";

type FieldKey = "commission_pct" | "delivery_payout" | "min_order_amount" | "max_delivery_radius_km";

const FIELDS: { key: FieldKey; label: string; help: string; suffix: string; prefix?: string }[] = [
  { key: "commission_pct", label: "Platform Commission", help: "Commission percentage on each order", suffix: "%" },
  { key: "delivery_payout", label: "Delivery Partner Payout", help: "Base payout per delivery", suffix: "", prefix: "₹" },
  { key: "min_order_amount", label: "Min Order Amount", help: "Minimum order value for delivery", suffix: "", prefix: "₹" },
  { key: "max_delivery_radius_km", label: "Max Delivery Radius", help: "Maximum distance for deliveries", suffix: " km" },
];

export function SettingsTab() {
  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<FieldKey | null>(null);
  const [draftValue, setDraftValue] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const s: PlatformSettings = await apiFetch("/admin/settings");
      setSettings(s);
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

  function startEdit(field: FieldKey, currentValue: string) {
    setEditingField(field);
    setDraftValue(currentValue);
  }

  async function saveField(field: FieldKey) {
    setSaving(true);
    try {
      const updated: PlatformSettings = await apiFetch("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ [field]: draftValue }),
      });
      setSettings(updated);
      setEditingField(null);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleGateway(key: string) {
    if (!settings) return;
    setSaving(true);
    try {
      const nextGateways = settings.payment_gateways.map((g) => (g.key === key ? { ...g, enabled: !g.enabled } : g));
      const updated: PlatformSettings = await apiFetch("/admin/settings", {
        method: "PUT",
        body: JSON.stringify({ payment_gateways: nextGateways }),
      });
      setSettings(updated);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-8"><p className="text-sm text-gray-400">Loading…</p></div>;
  if (error && !settings) return <div className="p-8"><p className="text-sm text-red-500">{error}</p></div>;
  if (!settings) return null;

  return (
    <div className="p-8 max-w-3xl space-y-5">
      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="bg-white rounded-2xl border border-gray-100 p-6">
        <h3 className="font-semibold text-gray-900 mb-1">Platform Settings</h3>
        <div className="divide-y divide-gray-50 mt-3">
          {FIELDS.map((f) => {
            const rawValue = settings[f.key];
            const isEditing = editingField === f.key;
            return (
              <div key={f.key} className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">{f.label}</p>
                  <p className="text-xs text-gray-400">{f.help}</p>
                </div>
                {isEditing ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      value={draftValue}
                      onChange={(e) => setDraftValue(e.target.value)}
                      className="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-right focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={() => saveField(f.key)}
                      disabled={saving}
                      className="text-xs font-medium bg-blue-600 text-white rounded-lg px-3 py-1.5 disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingField(null)}
                      disabled={saving}
                      className="text-xs font-medium text-gray-500 rounded-lg px-2 py-1.5"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-blue-600">
                      {f.prefix ?? ""}
                      {Number(rawValue).toLocaleString("en-IN")}
                      {f.suffix}
                    </span>
                    <button
                      onClick={() => startEdit(f.key, String(rawValue))}
                      className="text-xs font-medium border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
                    >
                      Edit
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-6">
        <h3 className="font-semibold text-gray-900 mb-1">Payment Gateway</h3>
        <div className="divide-y divide-gray-50 mt-3">
          {settings.payment_gateways.map((g) => (
            <div key={g.key} className="flex items-center justify-between py-4">
              <p className="text-sm font-medium text-gray-900">{g.name}</p>
              <div className="flex items-center gap-3">
                <span
                  className={`text-xs font-medium rounded-full px-2.5 py-1 ${
                    g.primary ? "bg-emerald-50 text-emerald-600" : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {g.primary ? "Primary" : "Active"}
                </span>
                <button
                  role="switch"
                  aria-checked={g.enabled}
                  onClick={() => toggleGateway(g.key)}
                  disabled={saving}
                  className={`relative w-10 h-5.5 rounded-full transition-colors disabled:opacity-50 ${
                    g.enabled ? "bg-blue-600" : "bg-gray-200"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 w-4.5 h-4.5 rounded-full bg-white shadow transition-transform ${
                      g.enabled ? "translate-x-[1.15rem]" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
