// Shared types + formatting for a shop's public info: opening hours,
// open/closed status, delivery terms. Mirrors backend/app/core/shop_hours.py.
// All times are shown in the SHOP's timezone (not the visitor's), because
// "opens at 9:00 AM" means the shop's 9 AM.

export type OpenInfo = {
  is_open: boolean;
  state: "open" | "closed_hours" | "temporarily_closed";
  opens_at: string | null;
  closes_at: string | null;
  message: string | null;
};

export const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type DayKey = (typeof DAY_KEYS)[number];
export type HoursRange = { open: string; close: string };
export type OpeningHours = Record<DayKey, HoursRange[]>;

export const DAY_LABELS: Record<DayKey, string> = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday",
};

export type ShopTerms = {
  delivery_fee?: string | number | null;
  free_delivery_above?: string | number | null;
  min_order_amount?: string | number | null;
  prep_time_minutes?: number | null;
  delivery_time_minutes?: number | null;
};

export const DEFAULT_TZ = "Asia/Kolkata";

export function inr(value: string | number | null | undefined): string {
  const n = Number(value ?? 0);
  if (Number.isNaN(n)) return "₹0";
  return Number.isInteger(n) ? `₹${n.toLocaleString("en-IN")}` : `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** "09:30" -> "9:30 AM"; "24:00" -> "midnight". */
export function clock(hhmm: string): string {
  if (hhmm === "24:00") return "midnight";
  const [h, m] = hhmm.split(":").map(Number);
  const suffix = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, "0")} ${suffix}`;
}

function ymd(d: Date, tz: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz }).format(d);
}

/** "6:30 PM", "tomorrow 9:00 AM" or "Mon 9:00 AM", in the shop's timezone. */
export function whenText(iso: string | null | undefined, tz: string = DEFAULT_TZ, now: Date = new Date()): string {
  if (!iso) return "";
  const d = new Date(iso);
  const time = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: tz }).format(d);
  const today = ymd(now, tz);
  if (ymd(d, tz) === today) return time;
  const tomorrow = ymd(new Date(now.getTime() + 24 * 3600 * 1000), tz);
  if (ymd(d, tz) === tomorrow) return `tomorrow ${time}`;
  const day = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: tz }).format(d);
  return `${day} ${time}`;
}

export function todayKey(tz: string = DEFAULT_TZ, now: Date = new Date()): DayKey {
  const short = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: tz }).format(now).toLowerCase().slice(0, 3);
  return (DAY_KEYS as readonly string[]).includes(short) ? (short as DayKey) : "mon";
}

export function statusLabel(info: OpenInfo | null | undefined, tz: string = DEFAULT_TZ): { label: string; tone: "open" | "closed" | "away" } | null {
  if (!info) return null;
  if (info.is_open) {
    return { label: info.closes_at ? `Open · closes ${whenText(info.closes_at, tz)}` : "Open", tone: "open" };
  }
  if (info.state === "temporarily_closed") {
    return { label: info.opens_at ? `Temporarily closed · back ${whenText(info.opens_at, tz)}` : "Temporarily closed", tone: "away" };
  }
  return { label: info.opens_at ? `Closed · opens ${whenText(info.opens_at, tz)}` : "Closed", tone: "closed" };
}

export function isFullDay(ranges: HoursRange[]): boolean {
  return ranges.length === 1 && ranges[0].open === "00:00" && ranges[0].close === "24:00";
}

export function rangesText(ranges: HoursRange[] | undefined): string {
  if (!ranges || ranges.length === 0) return "Closed";
  if (isFullDay(ranges)) return "Open 24 hours";
  return ranges.map((r) => `${clock(r.open)} – ${clock(r.close)}`).join(", ");
}

/** ["Delivery ₹30", "Free above ₹500", "Min. order ₹150"] — only what applies. */
export function deliveryTerms(t: ShopTerms): string[] {
  const out: string[] = [];
  const fee = Number(t.delivery_fee ?? 0);
  out.push(fee > 0 ? `Delivery ${inr(fee)}` : "Free delivery");
  if (fee > 0 && t.free_delivery_above != null && Number(t.free_delivery_above) > 0) {
    out.push(`Free above ${inr(t.free_delivery_above)}`);
  }
  if (Number(t.min_order_amount ?? 0) > 0) out.push(`Min. order ${inr(t.min_order_amount)}`);
  return out;
}

export function emptyHours(): OpeningHours {
  return { mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: [] };
}

/** An order's expected time as plain text: "between 6:00 PM and 7:00 PM" / "by 6:30 PM". */
export function etaText(
  o: { eta_at?: string | null; slot_start?: string | null; slot_end?: string | null },
  tz: string = DEFAULT_TZ,
): string | null {
  if (o.slot_start && o.slot_end) {
    return `between ${whenText(o.slot_start, tz)} and ${whenText(o.slot_end, tz).replace("tomorrow ", "")}`;
  }
  if (o.eta_at) return `by ${whenText(o.eta_at, tz)}`;
  return null;
}
