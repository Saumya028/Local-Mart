export type AdminUser = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  created_at: string;
  is_suspended: boolean;
  orders_count: number;
};

export type AdminShop = {
  id: string;
  name: string;
  category: string;
  rating: number;
  is_active: boolean;
  approval_status: "pending" | "approved" | "rejected";
  docs_status: "pending" | "submitted" | "verified";
  documents: { name: string; doc_type: string; url: string }[];
  rejection_reason: string | null;
  created_at: string;
  owner_id: string;
  owner_email: string;
  owner_name: string | null;
  location: string | null;
};

export type DashboardSummary = {
  total_shops: number;
  shops_added_this_month: number;
  total_users: number;
  users_added_this_week: number;
  monthly_orders: number;
  monthly_orders_change_pct: number | null;
  platform_revenue: string;
  platform_revenue_change_pct: number | null;
};

export type UsersSummary = {
  total_customers: number;
  shop_owners: number;
  delivery_partners: number;
};

export type MonthPoint = { label: string; value: string };

export type CategoryShare = { category: string; pct: number };

export type PaymentGateway = { key: string; name: string; enabled: boolean; primary: boolean };

export type PlatformSettings = {
  commission_pct: string;
  delivery_payout: string;
  min_order_amount: string;
  max_delivery_radius_km: string;
  payment_gateways: PaymentGateway[];
  updated_at: string;
};

export function formatINR(value: string | number, options?: { compact?: boolean }): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return `₹${value}`;
  if (options?.compact) {
    if (n >= 10000000) return `₹${(n / 10000000).toFixed(2)}Cr`;
    if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
    if (n >= 1000) return `₹${(n / 1000).toFixed(1)}K`;
  }
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function formatCompact(n: number): string {
  if (n >= 10000000) return `${(n / 10000000).toFixed(2)}Cr`;
  if (n >= 100000) return `${(n / 100000).toFixed(1)}L`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString("en-IN");
}

export function docsStatusMeta(status: string): { label: string; className: string } {
  if (status === "verified") return { label: "Documents Verified", className: "bg-emerald-50 text-emerald-600" };
  if (status === "submitted") return { label: "Documents Submitted", className: "bg-blue-50 text-blue-600" };
  return { label: "Documents Needed", className: "bg-amber-50 text-amber-600" };
}
export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export const CATEGORY_COLORS: Record<string, string> = {
  Groceries: "#2563eb",
  Grocery: "#2563eb",
  Bakery: "#10b981",
  Pharmacy: "#8b5cf6",
  Electronics: "#f59e0b",
  Fashion: "#ec4899",
  Food: "#ec4899",
};

const FALLBACK_COLORS = ["#2563eb", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899", "#06b6d4", "#84cc16"];

export function categoryColor(category: string, index: number): string {
  return CATEGORY_COLORS[category] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}
