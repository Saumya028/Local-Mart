import { StarRating } from "./StarRating";
import { RatingSummary as Summary } from "./types";

/** Big average + a 5→1 bar per star, each optionally a filter button. */
export function RatingSummaryPanel({
  summary,
  activeStar,
  onSelectStar,
}: {
  summary: Summary;
  activeStar?: number | null;
  onSelectStar?: (star: number | null) => void;
}) {
  return (
    <div className="flex flex-col sm:flex-row gap-6 sm:items-center">
      <div className="text-center sm:text-left shrink-0">
        <p className="text-4xl font-bold text-gray-900">{summary.count ? summary.average.toFixed(1) : "–"}</p>
        <StarRating value={summary.average} size={18} />
        <p className="text-xs text-gray-400 mt-1">
          {summary.count} review{summary.count === 1 ? "" : "s"}
        </p>
      </div>
      <div className="flex-1 space-y-1 min-w-0">
        {[5, 4, 3, 2, 1].map((star) => {
          const n = summary.distribution[String(star)] ?? 0;
          const pct = summary.count ? (n / summary.count) * 100 : 0;
          const active = activeStar === star;
          const row = (
            <>
              <span className="w-8 text-xs text-gray-600 text-right shrink-0">{star} ★</span>
              <span className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                <span className="block h-full bg-amber-400 rounded-full" style={{ width: `${pct}%` }} />
              </span>
              <span className="w-8 text-xs text-gray-400 shrink-0">{n}</span>
            </>
          );
          return onSelectStar ? (
            <button
              key={star}
              type="button"
              onClick={() => onSelectStar(active ? null : star)}
              aria-pressed={active}
              className={`w-full flex items-center gap-2 rounded px-1 py-0.5 hover:bg-gray-50 ${active ? "bg-amber-50" : ""}`}
            >
              {row}
            </button>
          ) : (
            <div key={star} className="flex items-center gap-2 px-1 py-0.5">
              {row}
            </div>
          );
        })}
      </div>
    </div>
  );
}
