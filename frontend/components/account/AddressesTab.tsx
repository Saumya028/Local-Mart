"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import AddressForm from "@/components/AddressForm";
import { Address } from "./types";

export function AddressesTab() {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    try {
      const data: Address[] = await apiFetch("/addresses");
      setAddresses(data);
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

  async function removeAddress(id: string) {
    setBusyId(id);
    try {
      await apiFetch(`/addresses/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  async function setDefault(id: string) {
    setBusyId(id);
    try {
      await apiFetch(`/addresses/${id}`, { method: "PUT", body: JSON.stringify({ is_default: true }) });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading addresses…</p>;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">Saved Addresses</h2>
        <button onClick={() => setShowForm(!showForm)} className="text-sm text-blue-600 hover:underline">
          {showForm ? "Cancel" : "+ Add address"}
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {showForm && (
        <AddressForm
          onSaved={() => {
            setShowForm(false);
            load();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {addresses.length === 0 ? (
        <p className="text-sm text-gray-400">No saved addresses yet.</p>
      ) : (
        <div className="space-y-2.5">
          {addresses.map((a) => (
            <div key={a.id} className="border border-gray-100 rounded-xl p-4 flex items-center justify-between">
              <div>
                <p className="font-medium text-sm text-gray-900">
                  {a.label} {a.is_default && <span className="text-xs text-emerald-600 font-normal">(default)</span>}
                </p>
                <p className="text-xs text-gray-500">
                  {a.line1}, {a.city}
                </p>
              </div>
              <div className="flex gap-3 text-xs shrink-0">
                {!a.is_default && (
                  <button onClick={() => setDefault(a.id)} disabled={busyId === a.id} className="text-blue-600 hover:underline disabled:opacity-50">
                    Set default
                  </button>
                )}
                <button onClick={() => removeAddress(a.id)} disabled={busyId === a.id} className="text-red-500 hover:underline disabled:opacity-50">
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
