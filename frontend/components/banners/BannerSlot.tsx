"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useViewerLocation } from "@/lib/useViewerLocation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Banner = {
  id: string;
  image_url: string;
  title: string | null;
  shop_id: string;
  shop_name: string;
  width: number;
  height: number;
};

// Shared across every BannerSlot instance and every remount (React Strict
// Mode, route changes, the location event firing twice). Without this the
// same /banners/public request was sent 3x per page view. Results are kept
// for a short window; concurrent identical requests share one promise.
const BANNER_TTL_MS = 60_000;
const bannerCache = new Map<string, { at: number; promise: Promise<Banner[]> }>();

function loadBanners(slot: string, lat: number, lng: number): Promise<Banner[]> {
  const key = `${slot}|${lat}|${lng}`;
  const hit = bannerCache.get(key);
  if (hit && Date.now() - hit.at < BANNER_TTL_MS) return hit.promise;

  const params = new URLSearchParams({ slot, lat: String(lat), lng: String(lng) });
  const promise = fetch(`${API_URL}/banners/public?${params}`)
    .then((r) => (r.ok ? (r.json() as Promise<Banner[]>) : []))
    .catch(() => {
      bannerCache.delete(key); // don't cache failures
      return [] as Banner[];
    });
  bannerCache.set(key, { at: Date.now(), promise });
  return promise;
}

/**
 * One pre-decided banner spot (e.g. "home_top"). Asks the API for banners
 * from shops near THIS visitor — the server does the distance check, so
 * someone outside a shop's locality never receives its banner. Renders
 * nothing when there is nothing to show, so an empty spot leaves no gap.
 * Clicking a banner opens the advertiser's shop page.
 */
export function BannerSlot({
  slot,
  promptForLocation = false,
  className = "",
}: {
  slot: string;
  // Show a small "share your location" button when we don't know where the
  // visitor is. Enable on ONE slot per page so it isn't repeated.
  promptForLocation?: boolean;
  className?: string;
}) {
  const { loc, status, request } = useViewerLocation();
  const [banners, setBanners] = useState<Banner[]>([]);
  const [index, setIndex] = useState(0);

  // Depend on the primitive coordinates, not the `loc` object: the hook
  // hands back a NEW object each time it re-syncs, which used to re-run this
  // effect (and re-fetch) even though the position hadn't changed.
  const lat = loc?.lat;
  const lng = loc?.lng;

  useEffect(() => {
    if (lat === undefined || lng === undefined) {
      setBanners([]);
      return;
    }
    let cancelled = false;
    loadBanners(slot, lat, lng).then((data) => {
      if (!cancelled) {
        setBanners(data);
        setIndex(0);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [slot, lat, lng]);

  // Rotate when several nearby shops advertise in the same spot.
  useEffect(() => {
    if (banners.length < 2) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % banners.length), 6000);
    return () => clearInterval(t);
  }, [banners.length]);

  if (!loc) {
    if (!promptForLocation || status === "denied" || status === "unsupported") return null;
    return (
      <div className={`max-w-6xl mx-auto px-6 ${className}`}>
        <button
          onClick={request}
          disabled={status === "asking"}
          className="text-sm text-blue-600 border border-blue-200 rounded-full px-4 py-1.5 hover:bg-blue-50 disabled:opacity-50"
        >
          {status === "asking" ? "Locating…" : "📍 Share your location to see offers from shops near you"}
        </button>
      </div>
    );
  }

  if (banners.length === 0) return null;
  const b = banners[index % banners.length];

  return (
    <div className={`max-w-6xl mx-auto px-6 ${className}`}>
      <Link
        href={`/store/${b.shop_id}`}
        onClick={() => {
          // Fire-and-forget click count; the navigation proceeds regardless.
          fetch(`${API_URL}/banners/${b.id}/click`, { method: "POST", keepalive: true }).catch(() => {});
        }}
        className="relative block w-full overflow-hidden rounded-2xl border border-gray-100 bg-gray-50"
        style={{ aspectRatio: `${b.width} / ${b.height}` }}
        aria-label={b.title ?? `Visit ${b.shop_name}`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- advertiser-uploaded Supabase Storage URL */}
        <img
          src={b.image_url}
          alt={b.title ?? b.shop_name}
          width={b.width}
          height={b.height}
          decoding="async"
          className="absolute inset-0 w-full h-full object-cover"
        />
      </Link>
      {banners.length > 1 && (
        <div className="flex justify-center gap-1.5 mt-2">
          {banners.map((x, i) => (
            <button
              key={x.id}
              onClick={() => setIndex(i)}
              aria-label={`Show banner ${i + 1}`}
              className={`w-1.5 h-1.5 rounded-full ${i === index % banners.length ? "bg-blue-600" : "bg-gray-300"}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
