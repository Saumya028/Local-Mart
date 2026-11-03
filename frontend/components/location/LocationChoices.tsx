"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { getCurrentPosition, saveDeliveryLocation, useViewerLocation } from "@/lib/useViewerLocation";

type SavedAddress = {
  id: string;
  label: string;
  line1: string;
  city: string;
  lat?: number | null;
  lng?: number | null;
  is_default: boolean;
};

/**
 * Lets the customer choose where to deliver: one of their saved addresses
 * (needs a map pin) or "Use current location". Shared by the header picker
 * and the "set your location" prompt shown before anything is chosen.
 */
export function LocationChoices({ onChosen }: { onChosen?: () => void }) {
  const router = useRouter();
  const { loggedIn } = useAuth();
  const { location } = useViewerLocation();
  const [addresses, setAddresses] = useState<SavedAddress[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loggedIn) {
      setAddresses([]);
      return;
    }
    apiFetch("/addresses")
      .then((rows: SavedAddress[]) => setAddresses(rows))
      .catch(() => setAddresses([]));
  }, [loggedIn]);

  function choose(label: string, lat: number, lng: number, addressId: string | null) {
    saveDeliveryLocation({ lat, lng, label, addressId });
    router.refresh();
    onChosen?.();
  }

  async function useCurrent() {
    setBusy(true);
    setError(null);
    try {
      const pos = await getCurrentPosition();
      choose("Current location", pos.lat, pos.lng, null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      {addresses.map((a) => {
        const pinned = a.lat != null && a.lng != null;
        const active = location?.addressId === a.id;
        return (
          <button
            key={a.id}
            type="button"
            disabled={!pinned}
            onClick={() => pinned && choose(a.label, a.lat as number, a.lng as number, a.id)}
            className={`w-full text-left border rounded-lg px-3 py-2 text-sm transition ${
              active ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:bg-gray-50"
            } disabled:opacity-60 disabled:cursor-not-allowed`}
          >
            <span className="font-medium text-gray-900">{a.label}</span>
            {a.is_default && <span className="text-xs text-emerald-600"> (default)</span>}
            <span className="block text-xs text-gray-500 truncate">
              {a.line1}, {a.city}
            </span>
            {!pinned && (
              <span className="block text-[11px] text-amber-700">
                No map pin yet — open My Account → Addresses and tap “Pin to my current location”.
              </span>
            )}
          </button>
        );
      })}
      <button
        type="button"
        onClick={useCurrent}
        disabled={busy}
        className="w-full text-sm font-medium text-blue-600 border border-blue-200 rounded-lg px-3 py-2 hover:bg-blue-50 disabled:opacity-50"
      >
        {busy ? "Locating…" : "📍 Use current location"}
      </button>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {!loggedIn && (
        <p className="text-[11px] text-gray-400">Sign in to pick one of your saved addresses instead.</p>
      )}
    </div>
  );
}
