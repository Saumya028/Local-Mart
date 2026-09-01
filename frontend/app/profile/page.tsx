"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import AddressForm from "@/components/AddressForm";

type Address = { id: string; label: string; line1: string; city: string; is_default: boolean };

export default function ProfilePage() {
  const { profile, loading: authLoading } = useAuth();
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loadingAddresses, setLoadingAddresses] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const addrs = await apiFetch("/addresses");
      setAddresses(addrs);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingAddresses(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function removeAddress(id: string) {
    await apiFetch(`/addresses/${id}`, { method: "DELETE" });
    load();
  }

  async function setDefault(id: string) {
    await apiFetch(`/addresses/${id}`, {
      method: "PUT",
      body: JSON.stringify({ is_default: true }),
    });
    load();
  }

  if (authLoading || loadingAddresses) {
    return (
      <main className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-red-500">Couldn&apos;t load your profile: {error}</p>
      </main>
    );
  }

  return (
    <main className="max-w-2xl mx-auto px-6 py-10 space-y-8">
      <section>
        <h1 className="text-2xl font-bold">My Profile</h1>
        <p className="text-sm text-gray-500 mt-1">{profile?.email}</p>
        <p className="text-xs text-gray-400">Role: {profile?.role}</p>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Addresses</h2>
          <button onClick={() => setShowForm(!showForm)} className="text-sm text-blue-600 underline">
            {showForm ? "Cancel" : "Add address"}
          </button>
        </div>

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
          <div className="space-y-3">
            {addresses.map((a) => (
              <div key={a.id} className="border rounded-lg p-4 flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">
                    {a.label}{" "}
                    {a.is_default && <span className="text-xs text-green-600">(default)</span>}
                  </p>
                  <p className="text-xs text-gray-500">
                    {a.line1}, {a.city}
                  </p>
                </div>
                <div className="flex gap-3 text-xs">
                  {!a.is_default && (
                    <button onClick={() => setDefault(a.id)} className="text-blue-600 underline">
                      Set default
                    </button>
                  )}
                  <button onClick={() => removeAddress(a.id)} className="text-red-500 underline">
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
