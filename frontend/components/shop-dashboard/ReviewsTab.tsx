"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { RatingSummaryPanel } from "@/components/reviews/RatingSummary";
import { ReviewCard } from "@/components/reviews/ReviewCard";
import { StarRating } from "@/components/reviews/StarRating";
import { DashboardReview, DashboardReviewList, DashboardReviewSummary } from "@/components/reviews/types";

const PAGE = 20;
type KindFilter = "all" | "product" | "shop";
type StatusFilter = "all" | "unreplied" | "replied" | "hidden";

function detail(err: unknown): string {
  const msg = (err as Error).message;
  const m = msg.match(/"detail":"([^"]+)"/);
  return m ? m[1] : msg;
}

/**
 * The owner's whole review desk for one shop: rating overview, every
 * product + shop review with filters, and per-review reply / hide.
 */
export function ReviewsTab({ shopId, onSummary }: { shopId: string; onSummary?: (unreplied: number) => void }) {
  const [summary, setSummary] = useState<DashboardReviewSummary | null>(null);
  const [list, setList] = useState<DashboardReviewList | null>(null);
  const [kind, setKind] = useState<KindFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [star, setStar] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replying, setReplying] = useState<string | null>(null); // review id with open reply box
  const [replyText, setReplyText] = useState("");
  const [hiding, setHiding] = useState<string | null>(null); // review id with open hide box
  const [hideReason, setHideReason] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const url = useCallback(
    (offset: number) =>
      `/dashboard/reviews?shop_id=${shopId}&kind=${kind}&status=${status}&limit=${PAGE}&offset=${offset}${star ? `&rating=${star}` : ""}`,
    [shopId, kind, status, star]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, l]: [DashboardReviewSummary, DashboardReviewList] = await Promise.all([
        apiFetch(`/dashboard/reviews/summary?shop_id=${shopId}`),
        apiFetch(url(0)),
      ]);
      setSummary(s);
      setList(l);
      onSummary?.(s.unreplied_count);
      setError(null);
    } catch (err) {
      setError(detail(err));
    } finally {
      setLoading(false);
    }
  }, [shopId, url, onSummary]);

  useEffect(() => {
    load();
  }, [load]);

  async function showMore() {
    if (!list) return;
    try {
      const more: DashboardReviewList = await apiFetch(url(list.items.length));
      setList({ ...more, items: [...list.items, ...more.items] });
    } catch (err) {
      setError(detail(err));
    }
  }

  async function act(review: DashboardReview, path: string, init: RequestInit) {
    setBusyId(review.id);
    try {
      await apiFetch(`/dashboard/reviews/${review.kind}/${review.id}/${path}`, init);
      setReplying(null);
      setHiding(null);
      setReplyText("");
      setHideReason("");
      await load();
    } catch (err) {
      setError(detail(err));
    } finally {
      setBusyId(null);
    }
  }

  const select = "text-sm border rounded-lg px-3 py-1.5 bg-white";

  return (
    <div className="space-y-6">
      {summary && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Stat label="Shop rating" value={summary.shop.count ? summary.shop.average.toFixed(1) : "–"} sub={`${summary.shop.count} shop review${summary.shop.count === 1 ? "" : "s"}`} />
            <Stat label="Product rating" value={summary.products.count ? summary.products.average.toFixed(1) : "–"} sub={`${summary.products.count} product review${summary.products.count === 1 ? "" : "s"}`} />
            <Stat label="Awaiting reply" value={String(summary.unreplied_count)} sub="reviews without a reply" highlight={summary.unreplied_count > 0} />
            <Stat label="Hidden" value={String(summary.hidden_count)} sub="not shown publicly" />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white rounded-2xl border border-gray-100 p-5">
              <p className="text-sm font-semibold text-gray-900 mb-3">Shop reviews</p>
              <RatingSummaryPanel summary={summary.shop} />
            </div>
            <div className="bg-white rounded-2xl border border-gray-100 p-5">
              <p className="text-sm font-semibold text-gray-900 mb-3">Product reviews</p>
              <RatingSummaryPanel summary={summary.products} />
            </div>
          </div>
        </>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Review type" value={kind} onChange={(e) => setKind(e.target.value as KindFilter)} className={select}>
          <option value="all">Products &amp; shop</option>
          <option value="product">Product reviews</option>
          <option value="shop">Shop reviews</option>
        </select>
        <select aria-label="Review status" value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)} className={select}>
          <option value="all">All</option>
          <option value="unreplied">Needs reply</option>
          <option value="replied">Replied</option>
          <option value="hidden">Hidden</option>
        </select>
        <select
          aria-label="Stars"
          value={star ?? ""}
          onChange={(e) => setStar(e.target.value ? Number(e.target.value) : null)}
          className={select}
        >
          <option value="">Any rating</option>
          {[5, 4, 3, 2, 1].map((n) => (
            <option key={n} value={n}>
              {n} star{n === 1 ? "" : "s"}
            </option>
          ))}
        </select>
        {list && <span className="text-xs text-gray-400 ml-auto">{list.total} review{list.total === 1 ? "" : "s"}</span>}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {loading && !list && <p className="text-sm text-gray-400">Loading reviews…</p>}
      {list && list.items.length === 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center text-sm text-gray-500">
          No reviews match these filters yet.
        </div>
      )}

      <div className={`space-y-3 ${loading ? "opacity-60" : ""}`}>
        {list?.items.map((r) => {
          const busy = busyId === r.id;
          return (
            <div key={`${r.kind}-${r.id}`} className="bg-white rounded-2xl border border-gray-100 px-5 pt-3">
              <div className="flex items-center gap-2 flex-wrap text-xs">
                <span className={`rounded-full px-2 py-0.5 font-medium ${r.kind === "shop" ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-600"}`}>
                  {r.kind === "shop" ? "Shop review" : r.product_name ?? "Product"}
                </span>
                {r.is_hidden && <span className="rounded-full px-2 py-0.5 bg-red-50 text-red-600 font-medium">Hidden</span>}
                {!r.reply_text && !r.is_hidden && <span className="rounded-full px-2 py-0.5 bg-amber-50 text-amber-700 font-medium">Needs reply</span>}
              </div>
              {r.is_hidden && r.hidden_reason && (
                <p className="text-xs text-red-500 mt-1">Hidden because: {r.hidden_reason}</p>
              )}

              <ReviewCard
                review={r}
                shopName="you"
                footer={
                  <div className="space-y-2">
                    <div className="flex items-center gap-4 text-sm">
                      <button
                        disabled={busy}
                        onClick={() => {
                          setReplying(replying === r.id ? null : r.id);
                          setReplyText(r.reply_text ?? "");
                          setHiding(null);
                        }}
                        className="text-blue-600 hover:underline disabled:opacity-50"
                      >
                        {r.reply_text ? "Edit reply" : "Reply"}
                      </button>
                      {r.reply_text && (
                        <button
                          disabled={busy}
                          onClick={() => act(r, "reply", { method: "DELETE" })}
                          className="text-gray-500 hover:underline disabled:opacity-50"
                        >
                          Delete reply
                        </button>
                      )}
                      {r.is_hidden ? (
                        <button
                          disabled={busy}
                          onClick={() => act(r, "visibility", { method: "PATCH", body: JSON.stringify({ hidden: false }) })}
                          className="text-emerald-600 hover:underline disabled:opacity-50"
                        >
                          Show again
                        </button>
                      ) : (
                        <button
                          disabled={busy}
                          onClick={() => {
                            setHiding(hiding === r.id ? null : r.id);
                            setHideReason("");
                            setReplying(null);
                          }}
                          className="text-red-500 hover:underline disabled:opacity-50"
                        >
                          Hide
                        </button>
                      )}
                    </div>

                    {replying === r.id && (
                      <div className="space-y-2 pb-3">
                        <textarea
                          value={replyText}
                          onChange={(e) => setReplyText(e.target.value)}
                          maxLength={1000}
                          rows={3}
                          placeholder="Write a public reply — customers will see it under the review."
                          className="w-full border rounded-lg px-3 py-2 text-sm"
                        />
                        <button
                          disabled={busy || !replyText.trim()}
                          onClick={() => act(r, "reply", { method: "PUT", body: JSON.stringify({ text: replyText }) })}
                          className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-1.5 disabled:opacity-50"
                        >
                          {busy ? "Posting…" : "Post reply"}
                        </button>
                      </div>
                    )}

                    {hiding === r.id && (
                      <div className="space-y-2 pb-3">
                        <p className="text-xs text-gray-500">
                          A hidden review disappears from your public page and from your average rating. Only hide reviews that
                          break the rules (abuse, spam, not about your shop).
                        </p>
                        <input
                          value={hideReason}
                          onChange={(e) => setHideReason(e.target.value)}
                          maxLength={300}
                          placeholder="Reason (required)"
                          className="w-full border rounded-lg px-3 py-2 text-sm"
                        />
                        <button
                          disabled={busy || !hideReason.trim()}
                          onClick={() => act(r, "visibility", { method: "PATCH", body: JSON.stringify({ hidden: true, reason: hideReason }) })}
                          className="bg-red-600 text-white text-sm font-medium rounded-lg px-4 py-1.5 disabled:opacity-50"
                        >
                          {busy ? "Hiding…" : "Hide review"}
                        </button>
                      </div>
                    )}
                  </div>
                }
              />
            </div>
          );
        })}
      </div>

      {list && list.items.length < list.total && (
        <button onClick={showMore} className="text-sm text-blue-600 hover:underline">
          Show more
        </button>
      )}
    </div>
  );
}

function Stat({ label, value, sub, highlight }: { label: string; value: string; sub: string; highlight?: boolean }) {
  return (
    <div className={`rounded-2xl border p-4 bg-white ${highlight ? "border-amber-200" : "border-gray-100"}`}>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1 flex items-center gap-2">
        {value}
        {label.endsWith("rating") && value !== "–" && <StarRating value={Number(value)} size={14} />}
      </p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  );
}
