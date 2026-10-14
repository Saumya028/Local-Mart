"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { StarInput } from "./StarInput";
import { MyReview, ReviewKind, reviewsPath } from "./types";

/**
 * Write or edit a review of a product or a shop. Used from the product
 * and store pages, the order page, and My Account > My Reviews — which is
 * why it takes the target as props instead of fetching anything itself.
 */
export function ReviewFormModal({
  kind,
  targetId,
  targetName,
  existing,
  onClose,
  onSaved,
}: {
  kind: ReviewKind;
  targetId: string;
  targetName: string;
  existing?: MyReview | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [rating, setRating] = useState(existing?.rating ?? 0);
  const [title, setTitle] = useState(existing?.title ?? "");
  const [body, setBody] = useState(existing?.body ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // apiFetch throws "API error 409 [request_id=…]: {"detail":"…"}" — pull
  // the human sentence out rather than showing that raw string.
  function friendly(err: unknown): string {
    const msg = (err as Error).message;
    const m = msg.match(/"detail":"([^"]+)"/);
    if (m) return m[1];
    return /\b422\b/.test(msg) ? "Please check your rating and text." : "Couldn't save your review. Please try again.";
  }

  async function submit() {
    if (rating < 1) {
      setError("Tap a star to choose a rating.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await apiFetch(existing ? `${reviewsPath(kind, targetId)}/mine` : reviewsPath(kind, targetId), {
        method: existing ? "PUT" : "POST",
        body: JSON.stringify({ rating, title: title || null, body: body || null }),
      });
      onSaved();
    } catch (err) {
      setError(friendly(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete your review?")) return;
    setBusy(true);
    try {
      await apiFetch(`${reviewsPath(kind, targetId)}/mine`, { method: "DELETE" });
      onSaved();
    } catch (err) {
      setError(friendly(err));
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Review ${targetName}`}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl p-5 space-y-4 max-h-[90vh] overflow-y-auto">
        <div>
          <h3 className="font-bold text-gray-900">{existing ? "Edit your review" : "Write a review"}</h3>
          <p className="text-sm text-gray-500 truncate">{targetName}</p>
        </div>

        <StarInput value={rating} onChange={setRating} />

        <div>
          <label className="text-xs font-medium text-gray-600">Title (optional)</label>
          <input
            value={title}
            maxLength={120}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Sum it up in a few words"
            className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-600">Your review (optional)</label>
          <textarea
            value={body}
            maxLength={2000}
            rows={4}
            onChange={(e) => setBody(e.target.value)}
            placeholder={kind === "product" ? "What did you like or dislike?" : "How was your experience with this shop?"}
            className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
          />
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex items-center gap-3">
          <button
            onClick={submit}
            disabled={busy}
            className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-50"
          >
            {busy ? "Saving…" : existing ? "Save changes" : "Submit review"}
          </button>
          <button onClick={onClose} disabled={busy} className="text-sm text-gray-500 hover:underline">
            Cancel
          </button>
          {existing && (
            <button onClick={remove} disabled={busy} className="ml-auto text-sm text-red-500 hover:underline">
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
