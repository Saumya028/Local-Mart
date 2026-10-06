"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import AddressForm from "@/components/AddressForm";
import { addressLines } from "@/lib/customerFields";

// crypto.randomUUID() isn't guaranteed to exist in every server runtime
// this component might briefly render under during SSR, so we fall back
// rather than risk a build-time crash on an older Node version.
function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

type Address = {
  id: string;
  label: string;
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

type CartShop = {
  id: string;
  name: string;
  pickup_enabled: boolean;
  address_line1: string | null;
  city: string | null;
  // Direct payment to the shop — see backend cart.py. UPI only counts if
  // the owner has it on AND gave a UPI id / QR to pay to.
  accepts_upi: boolean;
  accepts_cash: boolean;
};

type PayMethod = "upi" | "cash";

type CartItem = {
  product: { id: string; name: string; price: string; images: string[] };
  quantity: number;
  subtotal: string;
  shop: CartShop | null;
};

type CheckoutResponse = {
  orders: {
    id: string;
    shop_id: string;
    shop_name?: string | null;
    total_amount: string;
    fulfillment_type?: string;
    payment_method?: string | null;
  }[];
  total_amount: string;
};

// A shop can only actually be picked up from if its owner has the
// switch on AND it has an address on file — see Shop.pickup_enabled's
// docstring on the backend. Checked in exactly this shape wherever the
// frontend decides whether to offer the option.
function shopOffersPickup(shop: CartShop | null): boolean {
  return !!shop && shop.pickup_enabled && !!shop.address_line1;
}

export default function CheckoutPage() {
  // One idempotency key for this checkout attempt, generated once when
  // the page loads and reused across retries of that SAME attempt — this
  // is what lets the backend safely dedupe a retried request instead of
  // creating a second set of orders and charging twice.
  const idempotencyKey = useMemo(() => generateIdempotencyKey(), []);

  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [loadingCart, setLoadingCart] = useState(true);

  // Per-shop fulfillment choice — keyed by shop_id, defaulting every
  // shop to "delivery" (the only option that has always existed).
  // Cart items are already destined to become separate Order rows, one
  // per shop (see the backend Order model's docstring), so this maps
  // 1:1 onto how checkout actually splits the cart — a customer can
  // pick up from one shop in their cart while having another delivered,
  // in the same checkout.
  const [fulfillment, setFulfillment] = useState<Record<string, "delivery" | "pickup">>({});

  // Per-shop payment method, chosen straight away since the customer pays
  // each shop directly (UPI or cash) — nothing goes through LocalMart.
  const [payment, setPayment] = useState<Record<string, PayMethod>>({});

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [loadingAddresses, setLoadingAddresses] = useState(true);

  const [checkoutResult, setCheckoutResult] = useState<CheckoutResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadCart() {
    try {
      const data: { items: CartItem[] } = await apiFetch("/cart");
      setCartItems(data.items);
      // Only ever fills in shops we haven't already got a choice for —
      // preserves whatever the person already picked if this reloads.
      setFulfillment((prev) => {
        const next = { ...prev };
        for (const item of data.items) {
          if (item.shop && !(item.shop.id in next)) next[item.shop.id] = "delivery";
        }
        return next;
      });
      setPayment((prev) => {
        const next = { ...prev };
        for (const item of data.items) {
          const shop = item.shop;
          if (shop && !(shop.id in next)) {
            if (shop.accepts_upi) next[shop.id] = "upi";
            else if (shop.accepts_cash) next[shop.id] = "cash";
          }
        }
        return next;
      });
    } catch {
      // Cart failing to load surfaces below via the empty-state message;
      // no separate error banner needed for this one.
    } finally {
      setLoadingCart(false);
    }
  }

  async function loadAddresses() {
    try {
      const data: Address[] = await apiFetch("/addresses");
      setAddresses(data);
      const preferred = data.find((a) => a.is_default) ?? data[0];
      if (preferred) setSelectedAddressId(preferred.id);
      setShowAddForm(data.length === 0);
    } catch {
      // Likely not logged in — the address list will just show empty;
      // the "add address" form below still renders and will surface the
      // real error (e.g. "log in first") when they try to save one.
    } finally {
      setLoadingAddresses(false);
    }
  }

  useEffect(() => {
    loadCart();
    loadAddresses();
  }, []);

  const shopGroups = useMemo(() => {
    const byShop = new Map<string, { shop: CartShop | null; items: CartItem[] }>();
    for (const item of cartItems) {
      const key = item.shop?.id ?? "unknown";
      if (!byShop.has(key)) byShop.set(key, { shop: item.shop, items: [] });
      byShop.get(key)!.items.push(item);
    }
    return Array.from(byShop.values());
  }, [cartItems]);

  // At least one shop set to "delivery" means the address section is
  // needed at all — an all-pickup cart never touches the address book.
  const needsAddress = shopGroups.some(
    (g) => g.shop && (fulfillment[g.shop.id] ?? "delivery") === "delivery"
  );

  // A shop that accepts neither UPI nor cash can't be ordered from.
  const unpayableShop = shopGroups.find((g) => g.shop && !g.shop.accepts_upi && !g.shop.accepts_cash);

  async function startCheckout(e: FormEvent) {
    e.preventDefault();
    if (unpayableShop) {
      setError(`"${unpayableShop.shop?.name}" isn't accepting payments right now. Remove its items to continue.`);
      return;
    }
    if (needsAddress && !selectedAddressId) {
      setError("Please add or select a delivery address.");
      return;
    }

    const pickupShopIds = shopGroups
      .filter((g) => g.shop && fulfillment[g.shop.id] === "pickup")
      .map((g) => g.shop!.id);

    setLoading(true);
    setError(null);
    try {
      const data: CheckoutResponse = await apiFetch("/orders", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          address_id: needsAddress ? selectedAddressId : null,
          pickup_shop_ids: pickupShopIds,
          payment_methods: Object.fromEntries(
            shopGroups.filter((g) => g.shop).map((g) => [g.shop!.id, payment[g.shop!.id]])
          ),
        }),
      });
      // A single order goes straight to its page, where the UPI QR /
      // cash instructions are shown. Several orders (one per shop) land
      // on the summary below so each can be opened in turn.
      if (data.orders.length === 1) {
        window.location.href = `/orders/${data.orders[0].id}`;
        return;
      }
      setCheckoutResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (checkoutResult) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 space-y-4">
        <div className="text-center space-y-1">
          <p className="text-lg font-semibold">Orders placed — ₹{checkoutResult.total_amount}</p>
          <p className="text-sm text-gray-500">
            You pay each shop directly. Open each order to pay by UPI, or pay cash when you receive it.
          </p>
        </div>
        <div className="space-y-2">
          {checkoutResult.orders.map((o) => (
            <a
              key={o.id}
              href={`/orders/${o.id}`}
              className="flex items-center justify-between border rounded-lg p-3 text-sm hover:border-blue-400"
            >
              <span>
                Order #{o.id.slice(0, 8)}
                {o.fulfillment_type === "pickup" ? " (Pickup)" : ""}
                <span className="block text-xs text-gray-400">₹{o.total_amount}</span>
              </span>
              <span className="text-xs text-blue-600 underline">
                {payment[o.shop_id] === "cash" ? "View order" : "Pay now"}
              </span>
            </a>
          ))}
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-md mx-auto px-6 py-10 space-y-4">
      <h1 className="text-2xl font-bold">Checkout</h1>

      {loadingCart || loadingAddresses ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <form onSubmit={startCheckout} className="space-y-5">
          <div className="space-y-3">
            {shopGroups.map(({ shop, items }) => {
              const choice = shop ? fulfillment[shop.id] ?? "delivery" : "delivery";
              const offersPickup = shopOffersPickup(shop);
              return (
                <div key={shop?.id ?? "unknown"} className="border rounded-md p-3 space-y-2">
                  <p className="text-sm font-medium">{shop?.name ?? "Shop"}</p>
                  <ul className="text-xs text-gray-500 space-y-0.5">
                    {items.map((item) => (
                      <li key={item.product.id}>
                        {item.quantity}× {item.product.name}
                      </li>
                    ))}
                  </ul>
                  {offersPickup && shop && (
                    <div className="flex gap-3 pt-1">
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="radio"
                          name={`fulfillment-${shop.id}`}
                          checked={choice === "delivery"}
                          onChange={() => setFulfillment((prev) => ({ ...prev, [shop.id]: "delivery" }))}
                        />
                        Deliver to me
                      </label>
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="radio"
                          name={`fulfillment-${shop.id}`}
                          checked={choice === "pickup"}
                          onChange={() => setFulfillment((prev) => ({ ...prev, [shop.id]: "pickup" }))}
                        />
                        Pick up from shop
                      </label>
                    </div>
                  )}
                  {choice === "pickup" && shop && (
                    <p className="text-xs text-gray-400">
                      Pickup at: {shop.address_line1}
                      {shop.city ? `, ${shop.city}` : ""}
                    </p>
                  )}
                  {shop && (shop.accepts_upi || shop.accepts_cash) ? (
                    <div className="pt-2 border-t space-y-1">
                      <p className="text-xs font-medium text-gray-600">Pay {shop.name} directly</p>
                      <div className="flex flex-wrap gap-3">
                        {shop.accepts_upi && (
                          <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                            <input
                              type="radio"
                              name={`payment-${shop.id}`}
                              checked={payment[shop.id] === "upi"}
                              onChange={() => setPayment((prev) => ({ ...prev, [shop.id]: "upi" }))}
                            />
                            UPI (QR / app)
                          </label>
                        )}
                        {shop.accepts_cash && (
                          <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                            <input
                              type="radio"
                              name={`payment-${shop.id}`}
                              checked={payment[shop.id] === "cash"}
                              onChange={() => setPayment((prev) => ({ ...prev, [shop.id]: "cash" }))}
                            />
                            {choice === "pickup" ? "Cash at pickup" : "Cash on delivery"}
                          </label>
                        )}
                      </div>
                    </div>
                  ) : (
                    shop && (
                      <p className="text-xs text-red-500">This shop isn&apos;t accepting payments right now.</p>
                    )
                  )}
                </div>
              );
            })}
          </div>

          {needsAddress && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Delivery address</p>
              {addresses.map((a) => (
                <label
                  key={a.id}
                  className="flex items-start gap-2 border rounded-md p-3 text-sm cursor-pointer"
                >
                  <input
                    type="radio"
                    name="address"
                    checked={selectedAddressId === a.id}
                    onChange={() => setSelectedAddressId(a.id)}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-medium">{a.label}</span> — {addressLines(a).join(" · ")}
                  </span>
                </label>
              ))}

              {!showAddForm && (
                <button
                  type="button"
                  onClick={() => setShowAddForm(true)}
                  className="text-sm text-blue-600 underline"
                >
                  + Add a new address
                </button>
              )}

              {showAddForm && (
                <AddressForm
                  onSaved={() => {
                    setShowAddForm(false);
                    loadAddresses();
                  }}
                  onCancel={addresses.length > 0 ? () => setShowAddForm(false) : undefined}
                />
              )}
            </div>
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={
              loading ||
              (needsAddress && !selectedAddressId) ||
              cartItems.length === 0 ||
              !!unpayableShop
            }
            className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50"
          >
            {loading ? "Placing order…" : "Place order"}
          </button>

          <p className="text-xs text-gray-400 text-center">
            You pay the shop directly by UPI or cash — LocalMart never handles your money.
          </p>
        </form>
      )}
    </main>
  );
}
