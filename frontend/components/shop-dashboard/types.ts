export type ShopDocument = { name: string; doc_type: string; url: string };

export type Shop = {
  id: string;
  name: string;
  category: string;
  rating: number;
  is_active: boolean;
  created_at: string;
  approval_status: "pending" | "approved" | "rejected";
  docs_status: "pending" | "submitted" | "verified";
  documents: ShopDocument[];
  rejection_reason: string | null;
  address_line1: string | null;
  city: string | null;
  latitude: number | null;
  longitude: number | null;
};

export type Product = {
  id: string;
  shop_id: string;
  name: string;
  price: string;
  stock_qty: number;
  is_active: boolean;
  category: string;
  attributes: Record<string, string | number | boolean>;
};

export type DashboardOrder = {
  id: string;
  shop_id: string;
  status: string;
  total_amount: string;
  delivery_address: string;
  buyer_email: string;
  buyer_name: string | null;
  item_count: number;
  created_at: string;
};

export type Summary = { shop_id: string; shop_name: string; confirmed_orders: number; revenue: string };

export type DayPoint = { label: string; date: string; value: string };

export type TopProduct = { id: string; name: string; units_sold: number; revenue: string };

export type RecentOrderPreview = {
  id: string;
  buyer_name: string | null;
  buyer_email: string;
  item_count: number;
  total_amount: string;
  status: string;
  created_at: string;
};

export type DashboardMetrics = {
  today_revenue: string;
  today_orders: number;
  yesterday_revenue: string;
  yesterday_orders: number;
  pending_orders: number;
  urgent_pending_orders: number;
  avg_rating: number;
  week_revenue_total: string;
  week_revenue_change_pct: number | null;
  revenue_by_day: DayPoint[];
  top_products: TopProduct[];
  recent_orders: RecentOrderPreview[];
};

export type Analytics = {
  total_revenue: string;
  total_orders: number;
  unique_customers: number;
  conversion_rate_pct: number;
  orders_by_day: DayPoint[];
  revenue_by_day: DayPoint[];
};

// Mirrors the backend's ALLOWED_TRANSITIONS in app/core/order_status.py —
// kept here purely to decide which action button to show; the backend is
// what actually enforces this, so a mismatch here is a UI annoyance at
// worst, never a security gap. Deliberately no entry ever leads to
// "cancelled" — there is no reject/cancel action anywhere in this UI.
export const STATUS_TRANSITIONS: Record<string, { next: string; label: string }> = {
  confirmed: { next: "preparing", label: "Accept" },
  preparing: { next: "ready", label: "Mark Ready" },
  ready: { next: "delivered", label: "Mark Delivered" },
};

// Display labels + badge colors for every status an order can be in.
// "confirmed" is shown as "Pending" — from the shop's point of view, a
// confirmed (paid) order that hasn't been accepted yet IS the thing
// they're waiting to act on.
export const STATUS_META: Record<string, { label: string; className: string }> = {
  pending: { label: "Awaiting payment", className: "bg-gray-100 text-gray-500" },
  confirmed: { label: "Pending", className: "bg-amber-100 text-amber-700" },
  preparing: { label: "Preparing", className: "bg-blue-100 text-blue-700" },
  ready: { label: "Ready", className: "bg-violet-100 text-violet-700" },
  delivered: { label: "Delivered", className: "bg-emerald-100 text-emerald-700" },
  payment_failed: { label: "Payment failed", className: "bg-red-100 text-red-700" },
  cancelled: { label: "Cancelled", className: "bg-red-100 text-red-700" },
};

export function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, className: "bg-gray-100 text-gray-600" };
}

export function formatINR(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return `₹${value}`;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
