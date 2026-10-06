export type AccountOrder = {
  id: string;
  shop_id: string;
  shop_name: string | null;
  status: string;
  fulfillment_type: string;
  total_amount: string;
  item_count: number;
  delivery_address: string | null;
  created_at: string;
  // Direct-payment state — see backend app/models/payment.py. Null for
  // very old orders with no payment row.
  payment_method?: string | null;
  payment_status?: string | null;
};

export type PaymentInfo = {
  method: string;
  status: string;
  amount: string;
  payer_reference: string | null;
  payee_name: string | null;
  upi_id: string | null;
  upi_qr_url: string | null;
  upi_link: string | null;
  shop_accepts_upi: boolean;
  shop_accepts_cash: boolean;
};

export function paymentBadge(order: { payment_method?: string | null; payment_status?: string | null; status: string }): {
  label: string;
  className: string;
} | null {
  if (!order.payment_status || order.status === "cancelled") return null;
  if (order.payment_status === "paid") return { label: "Paid", className: "bg-emerald-50 text-emerald-600" };
  if (order.payment_status === "submitted") return { label: "Payment sent — awaiting shop", className: "bg-amber-50 text-amber-600" };
  if (order.payment_method === "cash") return { label: "Pay cash on receipt", className: "bg-gray-100 text-gray-600" };
  return { label: "Payment due (UPI)", className: "bg-red-50 text-red-600" };
}

export function isPickupOrder(order: { fulfillment_type: string }): boolean {
  return order.fulfillment_type === "pickup";
}

export function isFulfilled(status: string): boolean {
  return status === "delivered" || status === "picked_up";
}

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
  delivery_proof_photo_url?: string | null;
  shop: { id: string; name: string; address_line1?: string | null; city?: string | null } | null;
  payment?: PaymentInfo | null;
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
  difference_method?: string | null;
  difference_payer_reference?: string | null;
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
  // Newer fields are null on addresses saved before they existed.
  recipient_name?: string | null;
  phone?: string | null;
  line1: string;
  line2?: string | null;
  landmark?: string | null;
  city: string;
  state?: string | null;
  pincode?: string | null;
  is_default: boolean;
};

export type AccountProfile = {
  id: string;
  email: string | null;
  full_name: string | null;
  phone: string | null;
  role: string;
  created_at: string;
  date_of_birth?: string | null;
  gender?: string | null;
  customer_type?: "individual" | "business";
  business_name?: string | null;
  gstin?: string | null;
  pan?: string | null;
  gst_verified?: boolean;
};

const STATUS_META: Record<string, { label: string; className: string }> = {
  pending: { label: "Payment Pending", className: "bg-gray-100 text-gray-600" },
  cancelled: { label: "Cancelled", className: "bg-red-50 text-red-600" },
  confirmed: { label: "Confirmed", className: "bg-blue-50 text-blue-600" },
  preparing: { label: "Preparing", className: "bg-blue-50 text-blue-600" },
  packing: { label: "Packing", className: "bg-indigo-50 text-indigo-600" },
  out_for_delivery: { label: "Out for Delivery", className: "bg-amber-50 text-amber-600" },
  delivered: { label: "Delivered", className: "bg-emerald-50 text-emerald-600" },
  ready_for_pickup: { label: "Ready for Pickup", className: "bg-amber-50 text-amber-600" },
  picked_up: { label: "Picked Up", className: "bg-emerald-50 text-emerald-600" },
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
