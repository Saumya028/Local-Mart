import { StarRating } from "./StarRating";
import { Review, formatReviewDate } from "./types";

/** One review as the public sees it, with the shop's reply underneath. */
export function ReviewCard({
  review,
  shopName,
  footer,
}: {
  review: Review;
  // Label for the reply box ("Reply from <shop>").
  shopName?: string | null;
  footer?: React.ReactNode;
}) {
  return (
    <article className="border-b border-gray-100 py-4 last:border-b-0">
      <div className="flex items-center gap-2 flex-wrap">
        <StarRating value={review.rating} size={15} />
        {review.title && <h4 className="text-sm font-semibold text-gray-900">{review.title}</h4>}
      </div>
      <p className="text-xs text-gray-400 mt-1">
        {review.reviewer_name} · {formatReviewDate(review.created_at)}
        {review.edited_at && " · edited"}
        {review.verified_purchase && <span className="text-emerald-600"> · ✓ Verified purchase</span>}
      </p>
      {review.body && <p className="text-sm text-gray-700 mt-2 whitespace-pre-line break-words">{review.body}</p>}

      {review.reply_text && (
        <div className="mt-3 ml-3 pl-3 border-l-2 border-blue-100 bg-blue-50/40 rounded-r-lg py-2 pr-3">
          <p className="text-xs font-medium text-blue-700">
            Reply from {shopName || "the shop"}
            {review.replied_at && <span className="text-gray-400 font-normal"> · {formatReviewDate(review.replied_at)}</span>}
          </p>
          <p className="text-sm text-gray-700 mt-1 whitespace-pre-line break-words">{review.reply_text}</p>
        </div>
      )}
      {footer && <div className="mt-2">{footer}</div>}
    </article>
  );
}
