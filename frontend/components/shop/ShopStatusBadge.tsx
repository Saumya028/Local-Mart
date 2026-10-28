import { OpenInfo, statusLabel } from "@/lib/shopInfo";

const TONES = {
  open: "bg-emerald-50 text-emerald-700 border-emerald-100",
  closed: "bg-gray-100 text-gray-600 border-gray-200",
  away: "bg-amber-50 text-amber-700 border-amber-100",
} as const;

/** Small pill: "Open · closes 9:00 PM", "Closed · opens tomorrow 9:00 AM",
 *  "Temporarily closed · back Mon 10:00 AM". Renders nothing for shops
 *  whose API response predates hours support. */
export function ShopStatusBadge({
  info,
  timezone,
  className = "",
}: {
  info: OpenInfo | null | undefined;
  timezone?: string;
  className?: string;
}) {
  const s = statusLabel(info, timezone);
  if (!s) return null;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium border rounded-full px-2 py-0.5 ${TONES[s.tone]} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.tone === "open" ? "bg-emerald-500" : s.tone === "away" ? "bg-amber-500" : "bg-gray-400"}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}
