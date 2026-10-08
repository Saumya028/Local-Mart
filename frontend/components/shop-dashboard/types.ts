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
  // Owner-toggleable "Pick up from the shop" switch — see Sidebar.tsx's
  // shop card. True by default (every shop offers pickup unless the
  // owner turns it off), but checkout also independently requires
  // address_line1 to be set before actually offering pickup to a
  // customer.
  pickup_enabled: boolean;
  // Direct payments — customers pay the shop itself, never the platform.
  upi_id: string | null;
  upi_qr_url: string | null;
  accepts_upi: boolean;
  accepts_cash: boolean;
  // Paid promotion — see SponsorshipTab.
  is_sponsored?: boolean;
  sponsored_until?: string | null;
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
  images: string[];
  variant_group_id: string | null;
  variant_attributes: Record<string, string>;
};

export type DashboardOrder = {
  id: string;
  shop_id: string;
  status: string;
  // "delivery" or "pickup" — see Order.fulfillment_type on the backend.
  // Decides which of STATUS_TRANSITIONS_BY_FULFILLMENT below an order
  // follows and whether delivery_address or the shop's own address is
  // what's shown.
  fulfillment_type: string;
  total_amount: string;
  delivery_address: string | null;
  buyer_email: string;
  buyer_name: string | null;
  item_count: number;
  created_at: string;
  delivered_at: string | null;
  delivery_proof_photo_url: string | null;
  // Direct-payment state — see backend app/models/payment.py.
  payment_method: string | null;
  payment_status: string | null; // unpaid | submitted | paid
  payer_reference: string | null;
  payment_marked_at: string | null;
};

export type ReturnRequestType = "return" | "exchange";

export type DashboardReturn = {
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
  buyer_name: string | null;
  buyer_email: string | null;
  // Exchange price-difference settlement — see backend's
  // app/models/return_request.py. Always "0.00"/false/null for a plain
  // "return". A shop owner can't mark a positive-difference exchange
  // "completed" until difference_paid is true (enforced server-side in
  // update_return_status — this is just what lets the UI explain why the
  // button is disabled instead of the customer only finding out via a
  // failed request).
  price_difference: string;
  difference_paid: boolean;
  difference_method: string | null;
  difference_payer_reference: string | null;
  new_order_id: string | null;
};

// Mirrors the backend's SHOP_ALLOWED_TRANSITIONS in
// app/core/return_status.py — kept here purely to decide which action
// buttons to show; the backend is what actually enforces this, so a
// mismatch here is a UI annoyance at worst, never a security gap.
export const RETURN_STATUS_TRANSITIONS: Record<string, { next: string; label: string }[]> = {
  requested: [
    { next: "approved", label: "Approve" },
    { next: "rejected", label: "Reject" },
  ],
  approved: [{ next: "completed", label: "Mark Completed" }],
};

export const RETURN_STATUS_META: Record<string, { label: string; className: string }> = {
  requested: { label: "Requested", className: "bg-amber-100 text-amber-700" },
  approved: { label: "Approved", className: "bg-blue-100 text-blue-700" },
  completed: { label: "Completed", className: "bg-emerald-100 text-emerald-700" },
  rejected: { label: "Rejected", className: "bg-red-100 text-red-700" },
  cancelled: { label: "Cancelled", className: "bg-gray-100 text-gray-500" },
};

export function returnStatusMeta(status: string) {
  return RETURN_STATUS_META[status] ?? { label: status, className: "bg-gray-100 text-gray-600" };
}

export type Summary = { shop_id: string; shop_name: string; confirmed_orders: number; revenue: string };

// Staff (manager/delivery) accounts — see StaffTab.tsx. `role` is
// always "manager" or "delivery_partner" here (the backend never returns a
// customer/shop_owner/admin profile from GET /dashboard/staff).
export type StaffMember = {
  id: string;
  full_name: string | null;
  email: string | null;
  role: string;
  is_suspended: boolean;
  created_at: string;
};

export function staffRoleLabel(role: string): string {
  return role === "manager" ? "Manager" : role === "delivery_partner" ? "Delivery" : role;
}

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

// Mirrors the backend's two transition tables in
// app/core/order_status.py (DELIVERY_TRANSITIONS/PICKUP_TRANSITIONS) —
// kept here purely to decide which action button to show; the backend
// is what actually enforces this, so a mismatch here is a UI annoyance
// at worst, never a security gap. Deliberately no entry ever leads to
// "cancelled" — there is no reject/cancel action anywhere in this UI.
export const DELIVERY_STATUS_TRANSITIONS: Record<string, { next: string; label: string }> = {
  confirmed: { next: "preparing", label: "Accept" },
  preparing: { next: "packing", label: "Start Packing" },
  packing: { next: "out_for_delivery", label: "Out for Delivery" },
  out_for_delivery: { next: "delivered", label: "Mark Delivered" },
};

export const PICKUP_STATUS_TRANSITIONS: Record<string, { next: string; label: string }> = {
  confirmed: { next: "preparing", label: "Accept" },
  preparing: { next: "packing", label: "Start Packing" },
  packing: { next: "ready_for_pickup", label: "Ready for Pickup" },
  ready_for_pickup: { next: "picked_up", label: "Mark Picked Up" },
};

export function transitionsForFulfillment(
  fulfillmentType: string
): Record<string, { next: string; label: string }> {
  return fulfillmentType === "pickup" ? PICKUP_STATUS_TRANSITIONS : DELIVERY_STATUS_TRANSITIONS;
}

// Statuses whose transition requires a delivery-proof photo first (see
// OrdersTab's photo-capture modal) — mirrors the backend's
// DELIVERY_PROOF_REQUIRED_STATUSES. Deliberately just "delivered" —
// "picked_up" needs no photo, since the shop's own staff hands the
// order over in person and IS the witness.
export const PROOF_REQUIRED_STATUSES = new Set(["delivered"]);

// Display labels + badge colors for every status an order can be in,
// across BOTH fulfillment types. "confirmed" is shown as "Pending" —
// from the shop's point of view, a confirmed (paid) order that hasn't
// been accepted yet IS the thing they're waiting to act on.
export const STATUS_META: Record<string, { label: string; className: string }> = {
  pending: { label: "Awaiting payment", className: "bg-gray-100 text-gray-500" },
  confirmed: { label: "Pending", className: "bg-amber-100 text-amber-700" },
  preparing: { label: "Preparing", className: "bg-blue-100 text-blue-700" },
  packing: { label: "Packing", className: "bg-indigo-100 text-indigo-700" },
  out_for_delivery: { label: "Out for Delivery", className: "bg-violet-100 text-violet-700" },
  delivered: { label: "Delivered", className: "bg-emerald-100 text-emerald-700" },
  ready_for_pickup: { label: "Ready for Pickup", className: "bg-violet-100 text-violet-700" },
  picked_up: { label: "Picked Up", className: "bg-emerald-100 text-emerald-700" },
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
