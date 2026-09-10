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
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  subtotal: string;
};

export type OrderDetail = AccountOrder & { items: OrderDetailItem[] };

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
