"use client";

import { useCallback, useEffect, useState } from "react";

// The customer's approximate position, used ONLY to decide which nearby
// shops' banners to show. Coordinates are rounded to 3 decimals (~100 m)
// before they are cached or sent anywhere, the browser asks permission
// itself, and the server uses them for one query without storing them.
type Loc = { lat: number; lng: number };
const KEY = "lm_viewer_loc";
const EVENT = "lm-viewer-loc";
const MAX_AGE_MS = 60 * 60 * 1000; // re-check after an hour — people move

function readCached(): Loc | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Loc & { at: number };
    if (Date.now() - v.at > MAX_AGE_MS) return null;
    return { lat: v.lat, lng: v.lng };
  } catch {
    return null;
  }
}

function store(loc: Loc) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...loc, at: Date.now() }));
  } catch {
    /* private mode — location just isn't remembered between pages */
  }
  window.dispatchEvent(new Event(EVENT));
}

function locate(onOk: (l: Loc) => void, onFail: (denied: boolean) => void) {
  navigator.geolocation.getCurrentPosition(
    (pos) =>
      onOk({
        lat: Math.round(pos.coords.latitude * 1000) / 1000,
        lng: Math.round(pos.coords.longitude * 1000) / 1000,
      }),
    (err) => onFail(err.code === err.PERMISSION_DENIED),
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 5 * 60 * 1000 }
  );
}

export function useViewerLocation() {
  const [loc, setLoc] = useState<Loc | null>(null);
  const [status, setStatus] = useState<"idle" | "asking" | "denied" | "unsupported">("idle");

  useEffect(() => {
    const sync = () => setLoc(readCached());
    sync();
    window.addEventListener(EVENT, sync);

    // Already allowed on this site before? Refresh silently, no prompt.
    if (!readCached() && "geolocation" in navigator && navigator.permissions) {
      navigator.permissions
        .query({ name: "geolocation" as PermissionName })
        .then((p) => {
          if (p.state === "granted") locate(store, () => {});
          else if (p.state === "denied") setStatus("denied");
        })
        .catch(() => {});
    }
    return () => window.removeEventListener(EVENT, sync);
  }, []);

  // Called from a button click — the only time we trigger the browser's
  // permission prompt.
  const request = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setStatus("unsupported");
      return;
    }
    setStatus("asking");
    locate(
      (l) => {
        store(l);
        setStatus("idle");
      },
      (denied) => setStatus(denied ? "denied" : "idle")
    );
  }, []);

  return { loc, status, request };
}
