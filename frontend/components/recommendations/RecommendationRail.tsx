"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useViewerLocation } from "@/lib/useViewerLocation";
import { trackReco } from "@/lib/recoEvents";
import type { RecoResponse, RecoSurface } from "./types";

/**
 * A horizontally scrolling shelf of recommended products. Hides itself while
 * loading, on any error, and when there is nothing to show — a recommendation
 * problem must never leave a hole or an error on the page around it.
 */
export function RecommendationRail({
  title,
  surface,
  path,
  requiresAuth = false,
  refreshKey,
  limit = 8,
  className = "",
}: {
  title: string;
  surface: RecoSurface;
  path: string; // e.g. "/recommendations/home"
  requiresAuth?: boolean;
  refreshKey?: string | number; // refetch when this changes (e.g. cart contents)
  limit?: number;
  className?: string;
}) {
  const { loc } = useViewerLocation();
  const [data, setData] = useState<RecoResponse | null>(null);
  const [heading, setHeading] = useState(title);
  const seen = useRef<Set<string>>(new Set());
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const q = new URLSearchParams({ limit: String(limit) });
    if (loc) {
      q.set("lat", String(loc.lat));
      q.set("lng", String(loc.lng));
    }
    apiFetch(`${path}${path.includes("?") ? "&" : "?"}${q}`)
      .then((r: RecoResponse) => {
        if (cancelled) return;
        seen.current = new Set();
        setData(r);
        // home shelf: signed-out / holdout visitors get the non-personal title
        if (surface === "home" && r.variant !== "model") setHeading("Trending near you");
        else setHeading(title);
      })
      .catch(() => !cancelled && setData(null));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, loc?.lat, loc?.lng, refreshKey, limit, requiresAuth]);

  // one impression per product, only once the shelf is actually on screen
  useEffect(() => {
    const el = ref.current;
    if (!el || !data?.items.length) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        data.items.forEach((it, i) => {
          if (seen.current.has(it.id)) return;
          seen.current.add(it.id);
          trackReco({ surface, event: "impression", product_id: it.id, position: i, run_id: data.run_id, variant: data.variant });
        });
        obs.disconnect();
      },
      { threshold: 0.3 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [data, surface]);

  if (!data || data.items.length === 0) return null;

  return (
    <section ref={ref} className={className} aria-label={heading}>
      <h2 className="text-lg font-semibold text-gray-900 mb-3">{heading}</h2>
      <div className="flex gap-4 overflow-x-auto pb-2 -mx-1 px-1 snap-x">
        {data.items.map((it, i) => (
          <Link
            key={it.id}
            href={`/product/${it.id}`}
            onClick={() =>
              trackReco({ surface, event: "click", product_id: it.id, position: i, run_id: data.run_id, variant: data.variant })
            }
            className="snap-start shrink-0 w-40 sm:w-44 rounded-xl border border-gray-200 bg-white hover:shadow-md transition-shadow"
          >
            <div className="aspect-square bg-gray-100 rounded-t-xl overflow-hidden">
              {it.images?.[0] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={it.images[0]} alt={it.name} className="w-full h-full object-cover" loading="lazy" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-3xl text-gray-300">🛍️</div>
              )}
            </div>
            <div className="p-3 space-y-1">
              <p className="text-sm font-medium text-gray-900 line-clamp-2">{it.name}</p>
              <p className="text-sm font-semibold text-gray-900">₹{Number(it.price).toLocaleString("en-IN")}</p>
              {it.rating_count ? (
                <p className="text-xs text-amber-600">★ {Number(it.rating_avg).toFixed(1)} <span className="text-gray-400">({it.rating_count})</span></p>
              ) : null}
              {it.shop_name && (
                <p className="text-xs text-gray-500 truncate">
                  {it.shop_name}
                  {it.distance_km != null ? ` · ${it.distance_km.toFixed(1)} km` : ""}
                </p>
              )}
              {it.reason && <p className="text-[11px] text-blue-600 line-clamp-1">{it.reason}</p>}
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
