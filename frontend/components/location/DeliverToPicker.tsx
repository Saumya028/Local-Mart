"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { saveDeliveryLocation, useViewerLocation } from "@/lib/useViewerLocation";
import { LocationChoices } from "./LocationChoices";

type SavedAddress = { id: string; label: string; lat?: number | null; lng?: number | null; is_default: boolean };

/** "Deliver to: Home ▾" in the header. */
export function DeliverToPicker() {
  const router = useRouter();
  const { loggedIn } = useAuth();
  const { location, ready } = useViewerLocation();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  // On login with nothing chosen yet, start from the default saved address
  // (when it has a map pin) so the customer lands on shops that serve them.
  useEffect(() => {
    if (!ready || !loggedIn || location) return;
    let cancelled = false;
    apiFetch("/addresses")
      .then((rows: SavedAddress[]) => {
        if (cancelled) return;
        const pick = rows.find((a) => a.is_default && a.lat != null && a.lng != null) ?? rows.find((a) => a.lat != null && a.lng != null);
        if (pick) {
          saveDeliveryLocation({ lat: pick.lat as number, lng: pick.lng as number, label: pick.label, addressId: pick.id });
          router.refresh();
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [ready, loggedIn, location, router]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!ready) return null;

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-sm text-gray-700 border border-gray-200 rounded-full px-3 py-1.5 hover:bg-gray-50 max-w-[11rem]"
        aria-expanded={open}
      >
        <span aria-hidden>📍</span>
        <span className="truncate">{location ? location.label : "Set location"}</span>
        <span aria-hidden className="text-gray-400 text-xs">▾</span>
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-72 bg-white border border-gray-100 rounded-xl shadow-lg p-3 z-30 space-y-2">
          <p className="text-xs font-medium text-gray-500">Deliver to</p>
          <LocationChoices onChosen={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}
