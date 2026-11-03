"use client";

import { useCallback, useEffect, useState } from "react";

// The customer's DELIVERY LOCATION — the single place every "which shops can
// serve me" decision starts from (shop lists, search, recommendations,
// banners). It is either one of their saved addresses (with a map pin) or
// their browser's current position.
//
// It is kept in localStorage (for client components) AND mirrored into a
// cookie (so server-rendered pages like /, /stores and /search can ask the API
// for only the shops that deliver here). Coordinates are rounded to 3 decimals
// (~100 m) before they are stored or sent; checkout re-checks distance on the
// server using the exact address pin.
export type Loc = { lat: number; lng: number };
export type DeliveryLocation = Loc & { label: string; addressId?: string | null };

const KEY = "lm_viewer_loc";
const COOKIE = "lm_loc";
const EVENT = "lm-viewer-loc";

const round3 = (n: number) => Math.round(n * 1000) / 1000;

function readStored(): DeliveryLocation | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Partial<DeliveryLocation>;
    if (typeof v.lat !== "number" || typeof v.lng !== "number") return null;
    return { lat: v.lat, lng: v.lng, label: v.label || "Current location", addressId: v.addressId ?? null };
  } catch {
    return null;
  }
}

function writeCookie(loc: Loc | null) {
  try {
    document.cookie = loc
      ? `${COOKIE}=${loc.lat},${loc.lng}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`
      : `${COOKIE}=; path=/; max-age=0; SameSite=Lax`;
  } catch {
    /* cookies blocked — server pages will just ask for a location */
  }
}

export function saveDeliveryLocation(loc: DeliveryLocation | null) {
  try {
    if (loc) {
      const clean = { ...loc, lat: round3(loc.lat), lng: round3(loc.lng) };
      localStorage.setItem(KEY, JSON.stringify(clean));
      writeCookie(clean);
    } else {
      localStorage.removeItem(KEY);
      writeCookie(null);
    }
  } catch {
    if (loc) writeCookie({ lat: round3(loc.lat), lng: round3(loc.lng) });
  }
  window.dispatchEvent(new Event(EVENT));
}

/** Ask the browser for the current position (triggers its permission prompt). */
export function getCurrentPosition(): Promise<Loc> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("Your browser doesn't support location access."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      (err) =>
        reject(
          new Error(
            err.code === err.PERMISSION_DENIED
              ? "Location access was denied — allow it in your browser settings, or pick a saved address."
              : "Couldn't get your location. Try again in a moment."
          )
        ),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60 * 1000 }
    );
  });
}

export function useViewerLocation() {
  const [location, setLocation] = useState<DeliveryLocation | null>(null);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<"idle" | "asking" | "denied" | "unsupported">("idle");

  useEffect(() => {
    // Keep the same object when nothing changed so consumers don't re-render.
    const sync = () =>
      setLocation((prev) => {
        const next = readStored();
        if (prev && next && prev.lat === next.lat && prev.lng === next.lng && prev.label === next.label) return prev;
        return next;
      });
    sync();
    setReady(true);
    // Make sure the server can see a location the browser already has.
    const stored = readStored();
    if (stored && !document.cookie.includes(`${COOKIE}=`)) writeCookie(stored);
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);

  // "Use current location" — only ever called from a button click.
  const request = useCallback(async () => {
    setStatus("asking");
    try {
      const pos = await getCurrentPosition();
      saveDeliveryLocation({ ...pos, label: "Current location", addressId: null });
      setStatus("idle");
    } catch (err) {
      const msg = (err as Error).message;
      setStatus(msg.includes("denied") ? "denied" : msg.includes("support") ? "unsupported" : "idle");
    }
  }, []);

  const loc: Loc | null = location ? { lat: location.lat, lng: location.lng } : null;
  return { loc, location, ready, status, request };
}
