"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

/**
 * Turns /stores into a distance-filtered search: reads whatever's
 * already in the URL (q/category), adds lat/lng from the browser's
 * Geolocation API, and pushes the new URL — the page itself is a
 * server component that re-fetches from GET /shops using whatever
 * searchParams it finds, so this component's only job is getting
 * lat/lng into the URL (and back out again on "Clear").
 */
export function NearMeToggle({ active, radiusKm }: { active: boolean; radiusKm: number | null }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function pushWithParams(mutate: (params: URLSearchParams) => void) {
    const params = new URLSearchParams(searchParams.toString());
    mutate(params);
    router.push(`/stores?${params.toString()}`);
  }

  function handleNearMe() {
    if (!("geolocation" in navigator)) {
      setError("Your browser doesn't support location access.");
      return;
    }
    setLocating(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        pushWithParams((params) => {
          params.set("lat", String(pos.coords.latitude));
          params.set("lng", String(pos.coords.longitude));
        });
      },
      (err) => {
        setLocating(false);
        setError(
          err.code === err.PERMISSION_DENIED
            ? "Location access was denied — allow it in your browser settings to see shops near you."
            : "Couldn't get your location. Try again in a moment."
        );
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  function handleClear() {
    pushWithParams((params) => {
      params.delete("lat");
      params.delete("lng");
    });
  }

  if (active) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-full px-3 py-1.5">
          Showing shops within {radiusKm ?? 5} km of you
        </span>
        <button onClick={handleClear} className="text-blue-600 hover:underline text-xs font-medium">
          Clear
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleNearMe}
        disabled={locating}
        className="text-sm font-medium text-blue-600 border border-blue-200 rounded-full px-3 py-1.5 hover:bg-blue-50 disabled:opacity-50"
      >
        {locating ? "Locating…" : "📍 Show shops near me"}
      </button>
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
