"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { ReviewCard } from "@/components/reviews/ReviewCard";
import { ReviewFormModal } from "@/components/reviews/ReviewFormModal";
import { MyReview, MyReviewsResponse, ReviewKind } from "@/components/reviews/types";

type Target = { kind: ReviewKind; id: string; name: string; existing: MyReview | null };

/**
 * My Account > My Reviews: what's still waiting for a review (from
 * delivered / picked-up orders), and every review the customer has
 * written, with edit/delete via the same form used elsewhere.
 */
export function ReviewsTab({ onLoaded }: { onLoaded?: (count: number) => void }) {
  const [data, setData] = useState<MyReviewsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<Target | null>(null);

  async function load() {
    try {
      const d: MyReviewsResponse = await apiFetch("/reviews/mine");
      setData(d);
      onLoaded?.(d.reviews.length);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!data) return <p className="text-sm text-gray-400">Loading reviews…</p>;

  const nothing = data.reviews.length === 0 && data.pending_products.length === 0 && data.pending_shops.length === 0;

  return (
    <div className="space-y-6">
      {nothing && (
        <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
          <p className="font-semibold text-gray-900">No reviews yet</p>
          <p className="text-sm text-gray-500 mt-1 max-w-sm mx-auto">
            Once an order is delivered or picked up, you can rate the products and the shop here or from the order page.
          </p>
        </div>
      )}

      {(data.pending_products.length > 0 || data.pending_shops.length > 0) && (
        <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-3">
          <p className="text-sm font-semibold text-gray-900">Waiting for your review</p>
          {data.pending_products.map((p) => (
            <div key={p.product_id} className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gray-50 overflow-hidden shrink-0">
                {p.image && (
                  // eslint-disable-next-line @next/next/no-img-element -- user-uploaded Supabase Storage URL
                  <img src={p.image} alt="" className="w-full h-full object-contain" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-gray-900 truncate">{p.product_name}</p>
                {p.shop_name && <p className="text-xs text-gray-400 truncate">{p.shop_name}</p>}
              </div>
              <button
                onClick={() => setTarget({ kind: "product", id: p.product_id, name: p.product_name, existing: null })}
                className="text-sm text-amber-600 hover:underline whitespace-nowrap"
              >
                ☆ Rate
              </button>
            </div>
          ))}
          {data.pending_shops.map((s) => (
            <div key={s.shop_id} className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">🏪</div>
              <p className="text-sm text-gray-900 truncate flex-1">{s.shop_name} (shop)</p>
              <button
                onClick={() => setTarget({ kind: "shop", id: s.shop_id, name: s.shop_name, existing: null })}
                className="text-sm text-amber-600 hover:underline whitespace-nowrap"
              >
                ☆ Rate
              </button>
            </div>
          ))}
        </div>
      )}

      {data.reviews.length > 0 && (
        <div className="space-y-3">
          {data.reviews.map((r) => {
            const id = r.kind === "product" ? r.product_id! : r.shop_id;
            const href = r.kind === "product" ? `/product/${id}` : `/store/${id}`;
            return (
              <div key={`${r.kind}-${r.id}`} className="bg-white rounded-2xl border border-gray-100 px-5 pt-3">
                <div className="flex items-center justify-between gap-3">
                  <Link href={href} className="text-sm font-semibold text-gray-900 hover:underline truncate">
                    {r.target_name ?? (r.kind === "product" ? "Product" : "Shop")}
                    <span className="ml-2 text-xs font-normal text-gray-400">{r.kind === "shop" ? "Shop" : "Product"}</span>
                  </Link>
                  <button
                    onClick={() =>
                      setTarget({ kind: r.kind, id, name: r.target_name ?? "", existing: r })
                    }
                    className="text-sm text-blue-600 hover:underline whitespace-nowrap"
                  >
                    Edit
                  </button>
                </div>
                {r.is_hidden && (
                  <p className="text-xs text-amber-600 mt-1">The shop has hidden this review from public view.</p>
                )}
                <ReviewCard review={r} shopName={r.kind === "shop" ? r.target_name : undefined} />
              </div>
            );
          })}
        </div>
      )}

      {target && (
        <ReviewFormModal
          kind={target.kind}
          targetId={target.id}
          targetName={target.name}
          existing={target.existing}
          onClose={() => setTarget(null)}
          onSaved={() => {
            setTarget(null);
            load();
          }}
        />
      )}
    </div>
  );
}
