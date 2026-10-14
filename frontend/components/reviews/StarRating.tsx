// No "use client": used from server components (store/product pages,
// listing cards) as well as client ones.

/**
 * Read-only stars, with partial fill for averages (4.3 fills the fifth
 * star 30%). Purely visual — the numeric value is exposed to assistive
 * tech via aria-label instead.
 */
export function StarRating({ value, size = 16 }: { value: number; size?: number }) {
  const clamped = Math.max(0, Math.min(5, value));
  return (
    <span
      className="relative inline-block leading-none align-middle"
      style={{ fontSize: size }}
      role="img"
      aria-label={`${clamped.toFixed(1)} out of 5 stars`}
    >
      <span className="text-gray-200">★★★★★</span>
      <span
        className="absolute inset-0 overflow-hidden text-amber-400 whitespace-nowrap"
        style={{ width: `${(clamped / 5) * 100}%` }}
      >
        ★★★★★
      </span>
    </span>
  );
}

/**
 * The compact rating line used on listing cards and page headers:
 * "★ 4.3 (12)" once there are reviews, a muted "New" before that (a 0.0
 * rating would read as a bad score, not as "no reviews yet").
 */
export function RatingBadge({
  average,
  count,
  className = "text-xs",
}: {
  average: number;
  count: number;
  className?: string;
}) {
  if (!count) return <span className={`${className} text-gray-400`}>New</span>;
  return (
    <span className={`${className} text-amber-500`}>
      ★ {average.toFixed(1)} <span className="text-gray-400">({count})</span>
    </span>
  );
}
