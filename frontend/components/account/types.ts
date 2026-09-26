export type AccountOrder = {
  id: string;
  shop_id: string;
  shop_name: string | null;
  status: string;
  total_amount: string;
  item_count: number;
  delivery_address: string;
  created_at: string;
};

export type OrderDetailItem = {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  subtotal: string;
  returned_qty: number;
};

export type OrderDetail = AccountOrder & {
  items: OrderDetailItem[];
  delivered_at: string | null;
  shop: { id: string; name: string } | null;
};

export type ReturnRequestType = "return" | "exchange";

export type ReturnRequest = {
  id: string;
  order_id: string;
  order_item_id: string;
  shop_id: string;
  request_type: ReturnRequestType;
  quantity: number;
  reason: string;
  comment: string | null;
  exchange_product_id: string | null;
  refund_amount: string;
  status: "requested" | "approved" | "rejected" | "completed" | "cancelled";
  shop_note: string | null;
  created_at: string;
  resolved_at: string | null;
  product_name: string | null;
  exchange_product_name: string | null;
  shop_name: string | null;
  // Exchange price-difference settlement (see backend's
  // app/models/return_request.py). Always "0.00"/false/null for a plain
  // "return" — there's no replacement item to compare against.
  price_difference: string;
  difference_paid: boolean;
  new_order_id: string | null;
};

// Amazon/Flipkart-style canned reasons — the backend just stores whatever
// free-text string is sent, so this list is purely a frontend UX nicety
// (faster than typing) and can grow without any backend change.
export const RETURN_REASONS = [
  "Item is damaged or defective",
  "Wrong item was delivered",
  "Item doesn't fit / wrong size",
  "No longer needed",
  "Better price available elsewhere",
  "Item not as described",
  "Other",
];

const RETURN_STATUS_META: Record<string, { label: string; className: string }> = {
  requested: { label: "Requested", className: "bg-amber-50 text-amber-600" },
  approved: { label: "Approved", className: "bg-blue-50 text-blue-600" },
  completed: { label: "Completed", className: "bg-emerald-50 text-emerald-600" },
  rejected: { label: "Rejected", className: "bg-red-50 text-red-600" },
  cancelled: { label: "Cancelled", className: "bg-gray-100 text-gray-500" },
};

export function returnStatusMeta(status: string): { label: string; className: string } {
  return RETURN_STATUS_META[status] ?? { label: status, className: "bg-gray-100 text-gray-600" };
}

// Mirrors the backend's RETURN_WINDOW in app/core/return_status.py —
// purely cosmetic here (used to show "Return by <date>" / grey the
// button out client-side); the backend is what actually enforces it, so
// drifting from it would be a UI annoyance, never a security gap.
export const RETURN_WINDOW_DAYS = 7;

export function returnDeadline(deliveredAt: string): Date {
  const d = new Date(deliveredAt);
  d.setDate(d.getDate() + RETURN_WINDOW_DAYS);
  return d;
}

export function isWithinReturnWindow(deliveredAt: string | null): boolean {
  if (!deliveredAt) return false;
  return new Date() <= returnDeadline(deliveredAt);
}

export type WishlistProduct = {
  id: string;
  name: string;
  price: string;
  images: string[];
  stock_qty: number;
  is_active: boolean;
};

export type WishlistEntry = {
  id: string;
  product: WishlistProduct;
  shop_name: string | null;
  added_at: string;
};

export type Address = {
  id: string;
  label: string;
  line1: string;
  city: string;
  is_default: boolean;
};

export type AccountProfile = {
  id: string;
  email: string | null;
  full_name: string | null;
  phone: string | null;
  role: string;
  created_at: string;
};

const STATUS_META: Record<string, { label: string; className: string }> = {
  pending: { label: "Payment Pending", className: "bg-gray-100 text-gray-600" },
  confirmed: { label: "Confirmed", className: "bg-blue-50 text-blue-600" },
  preparing: { label: "Preparing", className: "bg-blue-50 text-blue-600" },
  ready: { label: "Out for Delivery", className: "bg-amber-50 text-amber-600" },
  delivered: { label: "Delivered", className: "bg-emerald-50 text-emerald-600" },
  payment_failed: { label: "Payment Failed", className: "bg-red-50 text-red-600" },
};

export function orderStatusMeta(status: string): { label: string; className: string } {
  return STATUS_META[status] ?? { label: status, className: "bg-gray-100 text-gray-600" };
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const isToday = d.toDateString() === today.toDateString();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();

  if (isToday) return `Today, ${d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}`;
  if (isYesterday) return "Yesterday";

  const diffDays = Math.floor((today.getTime() - d.getTime()) / 86400000);
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;

  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function initials(name: string | null, email: string | null, phone?: string | null): string {
  const source = name?.trim() || email || phone || "?";
  return source
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}
