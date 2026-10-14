"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { RatingSummaryPanel } from "./RatingSummary";
import { ReviewCard } from "./ReviewCard";
import { ReviewFormModal } from "./ReviewFormModal";
import { ReviewEligibility, ReviewKind, ReviewList as ReviewListData, reviewsPath } from "./types";

const PAGE = 10;
type Sort = "recent" | "highest" | "lowest";

/**
 * The whole reviews block for one product or shop: rating summary (the
 * bars filter by star), sort, the list with "Show more", and the
 * write/edit entry point — which only appears for people who are actually
 * allowed to review (GET …/reviews/mine decides, the backend enforces).
 */
export function ReviewList({
  kind,
  targetId,
  targetName,
  shopName,
}: {
  kind: ReviewKind;
  targetId: string;
  targetName: string;
  // Shown on the shop's replies; for a shop review it's just targetName.
  shopName?: string | null;
}) {
  const { loggedIn, loading: authLoading } = useAuth();
  const [data, setData] = useState<ReviewListData | null>(null);
  const [sort, setSort] = useState<Sort>("recent");
  const [star, setStar] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [eligibility, setEligibility] = useState<ReviewEligibility | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  const query = useCallback(
    (offset: number) =>
      `${reviewsPath(kind, targetId)}?sort=${sort}&limit=${PAGE}&offset=${offset}${star ? `&rating=${star}` : ""}`,
    [kind, targetId, sort, star]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await apiFetch(query(0)));
      setError(null);
    } catch {
      setError("Couldn't load reviews right now.");
    } finally {
      setLoading(false);
    }
  }, [query]);

  const loadEligibility = useCallback(async () => {
    if (!loggedIn) return setEligibility(null);
    try {
      setEligibility(await apiFetch(`${reviewsPath(kind, targetId)}/mine`));
    } catch {
      setEligibility(null);
    }
  }, [loggedIn, kind, targetId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!authLoading) loadEligibility();
  }, [authLoading, loadEligibility]);

  async function showMore() {
    if (!data) return;
    setLoadingMore(true);
    try {
      const more: ReviewListData = await apiFetch(query(data.items.length));
      setData({ ...more, items: [...data.items, ...more.items] });
    } catch {
      setError("Couldn't load more reviews.");
    } finally {
      setLoadingMore(false);
    }
  }

  function saved() {
    setFormOpen(false);
    load();
    loadEligibility();
  }

  const noun = kind === "product" ? "product" : "shop";

  return (
    <section className="space-y-5" aria-label={`${noun} reviews`}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-lg font-bold text-gray-900">{kind === "product" ? "Customer reviews" : "Shop reviews"}</h2>
        {!authLoading && (
          <div className="text-sm">
            {!loggedIn ? (
              <Link href="/login" className="text-blue-600 hover:underline">
                Log in to review
              </Link>
            ) : eligibility?.can_review ? (
              <button
                onClick={() => setFormOpen(true)}
                className="bg-blue-600 text-white font-medium rounded-lg px-4 py-2"
              >
                {eligibility.review ? "Edit your review" : "Write a review"}
              </button>
            ) : eligibility ? (
              <span className="text-xs text-gray-400">{eligibility.reason}</span>
            ) : null}
          </div>
        )}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {loading && !data && <p className="text-sm text-gray-400">Loading reviews…</p>}

      {data && data.summary.count === 0 && !star && (
        <p className="text-sm text-gray-400">No reviews yet — be the first once your order arrives.</p>
      )}

      {data && (data.summary.count > 0 || star) && (
        <>
          <RatingSummaryPanel summary={data.summary} activeStar={star} onSelectStar={setStar} />

          <div className="flex items-center justify-between gap-3 border-t pt-3">
            <p className="text-xs text-gray-500">
              {star ? `${data.total} review${data.total === 1 ? "" : "s"} with ${star} star${star === 1 ? "" : "s"}` : `${data.summary.count} reviews`}
              {star && (
                <button onClick={() => setStar(null)} className="ml-2 text-blue-600 hover:underline">
                  Clear filter
                </button>
              )}
            </p>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
              aria-label="Sort reviews"
              className="text-xs border rounded-md px-2 py-1 bg-white"
            >
              <option value="recent">Most recent</option>
              <option value="highest">Highest rated</option>
              <option value="lowest">Lowest rated</option>
            </select>
          </div>

          <div className={loading ? "opacity-60" : ""}>
            {data.items.map((r) => (
              <ReviewCard key={r.id} review={r} shopName={shopName ?? targetName} />
            ))}
          </div>

          {data.items.length < data.total && (
            <button
              onClick={showMore}
              disabled={loadingMore}
              className="text-sm text-blue-600 hover:underline disabled:opacity-50"
            >
              {loadingMore ? "Loading…" : "Show more reviews"}
            </button>
          )}
        </>
      )}

      {formOpen && (
        <ReviewFormModal
          kind={kind}
          targetId={targetId}
          targetName={targetName}
          existing={eligibility?.review}
          onClose={() => setFormOpen(false)}
          onSaved={saved}
        />
      )}
    </section>
  );
}
