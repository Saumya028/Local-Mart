"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";

type Shop = { id: string; name: string; category: string; is_active: boolean };
type Product = {
  id: string;
  shop_id: string;
  name: string;
  price: string;
  stock_qty: number;
  is_active: boolean;
  category: string;
};
type DashboardOrder = {
  id: string;
  shop_id: string;
  status: string;
  total_amount: string;
  buyer_email: string;
  created_at: string;
};
type Summary = { shop_id: string; shop_name: string; confirmed_orders: number; revenue: string };

// Mirrors the backend's ALLOWED_TRANSITIONS in shop_dashboard.py — kept
// here purely to decide which action buttons to show; the backend is
// what actually enforces this, so a mismatch here is a UI annoyance at
// worst, never a security gap.
const STATUS_TRANSITIONS: Record<string, string[]> = {
  confirmed: ["shipped", "cancelled"],
  shipped: ["delivered"],
};

export default function ShopDashboardPage() {
  const { profile, loading: authLoading, loggedIn } = useAuth();
  const [shops, setShops] = useState<Shop[]>([]);
  const [selectedShopId, setSelectedShopId] = useState<string | null>(null);
  const [tab, setTab] = useState<"products" | "orders" | "summary">("products");
  const [loadingShops, setLoadingShops] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canSell = profile?.role === "shop_owner" || profile?.role === "admin";

  async function loadShops() {
    try {
      const data: Shop[] = await apiFetch("/dashboard/shops");
      setShops(data);
      setSelectedShopId((prev) => prev ?? data[0]?.id ?? null);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingShops(false);
    }
  }

  useEffect(() => {
    // Only attempt the role-gated call once we actually know the role
    // allows it — this is what avoids the earlier bug pattern entirely:
    // a customer navigating here directly never even triggers a 403,
    // because we never ask the backend a question we already know the
    // answer to on the frontend.
    if (canSell) {
      loadShops();
    } else if (!authLoading) {
      setLoadingShops(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canSell, authLoading]);

  if (authLoading || (canSell && loadingShops)) {
    return (
      <main className="max-w-4xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  if (!loggedIn) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 space-y-3">
        <h1 className="text-2xl font-bold">Shop Dashboard</h1>
        <p className="text-sm text-gray-500">Log in to continue.</p>
      </main>
    );
  }

  // The core of this fix: selling is NOT self-service. A plain customer
  // account cannot create a shop or reach anything below this point —
  // becoming a shop_owner is an explicit promotion (see
  // backend/scripts/promote_user.py until the Admin Panel exists), not a
  // button any account can click. This mirrors exactly what the backend
  // enforces via require_role on every one of these endpoints.
  if (!canSell) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 space-y-3">
        <h1 className="text-2xl font-bold">Shop Dashboard</h1>
        <p className="text-sm text-gray-500">
          Selling isn&apos;t available for your account yet. Becoming a seller
          requires your account to be upgraded by a platform admin — this
          isn&apos;t something you can do yourself from here.
        </p>
      </main>
    );
  }

  // Reaching here means the account IS shop_owner/admin, but owns zero
  // shops yet (e.g. just promoted) — this is the "create your first
  // shop" screen, not a "become a seller" screen.
  if (shops.length === 0) {
    return (
      <main className="max-w-md mx-auto px-6 py-10">
        <CreateShopForm onCreated={loadShops} loadError={error} />
      </main>
    );
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-10 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Shop Dashboard</h1>
        {shops.length > 1 && (
          <select
            value={selectedShopId ?? ""}
            onChange={(e) => setSelectedShopId(e.target.value)}
            className="border rounded-md px-3 py-2 text-sm"
          >
            {shops.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="flex gap-4 border-b text-sm">
        {(["products", "orders", "summary"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 capitalize ${
              tab === t ? "border-b-2 border-blue-600 text-blue-600 font-medium" : "text-gray-500"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {selectedShopId && tab === "products" && <ProductsTab shopId={selectedShopId} />}
      {selectedShopId && tab === "orders" && <OrdersTab shopId={selectedShopId} />}
      {selectedShopId && tab === "summary" && <SummaryTab shopId={selectedShopId} />}
    </main>
  );
}

function CreateShopForm({
  onCreated,
  loadError,
}: {
  onCreated: () => void;
  loadError: string | null;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/shops", { method: "POST", body: JSON.stringify({ name, category }) });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h1 className="text-2xl font-bold">Create your shop</h1>
      <p className="text-sm text-gray-500">
        Your account is approved to sell — set up your first shop to get a
        dashboard for managing products and orders.
      </p>
      <input
        placeholder="Shop name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <input
        placeholder="Category (e.g. Groceries)"
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        required
        className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      {(error || loadError) && <p className="text-sm text-red-500">{error || loadError}</p>}
      <button
        type="submit"
        disabled={saving}
        className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50"
      >
        {saving ? "Creating…" : "Create shop"}
      </button>
    </form>
  );
}

function ProductsTab({ shopId }: { shopId: string }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const data: Product[] = await apiFetch(`/dashboard/products?shop_id=${shopId}`);
    setProducts(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  async function toggleActive(product: Product) {
    if (product.is_active) {
      await apiFetch(`/dashboard/products/${product.id}`, { method: "DELETE" });
    } else {
      await apiFetch(`/dashboard/products/${product.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: true }),
      });
    }
    load();
  }

  async function updateStock(product: Product, stockQty: number) {
    await apiFetch(`/dashboard/products/${product.id}`, {
      method: "PUT",
      body: JSON.stringify({ stock_qty: stockQty }),
    });
    load();
  }

  return (
    <div className="space-y-4 pt-4">
      <div className="flex justify-end">
        <button onClick={() => setShowForm(!showForm)} className="text-sm text-blue-600 underline">
          {showForm ? "Cancel" : "+ Add product"}
        </button>
      </div>

      {showForm && (
        <AddProductForm
          shopId={shopId}
          onSaved={() => {
            setShowForm(false);
            load();
          }}
        />
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Loading products…</p>
      ) : products.length === 0 ? (
        <p className="text-sm text-gray-400">No products yet.</p>
      ) : (
        <div className="space-y-3">
          {products.map((p) => (
            <div key={p.id} className="border rounded-lg p-4 flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">
                  {p.name} {!p.is_active && <span className="text-xs text-gray-400">(inactive)</span>}
                </p>
                <p className="text-xs text-gray-500">
                  {p.category} · ₹{p.price}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={0}
                  defaultValue={p.stock_qty}
                  onBlur={(e) => updateStock(p, Number(e.target.value))}
                  title="Stock quantity"
                  className="w-16 border rounded-md px-2 py-1 text-sm text-center"
                />
                <button onClick={() => toggleActive(p)} className="text-xs underline">
                  {p.is_active ? "Deactivate" : "Reactivate"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AddProductForm({ shopId, onSaved }: { shopId: string; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [price, setPrice] = useState("");
  const [stock, setStock] = useState("0");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/dashboard/products", {
        method: "POST",
        body: JSON.stringify({
          shop_id: shopId,
          name,
          category,
          price: Number(price),
          stock_qty: Number(stock),
        }),
      });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border rounded-lg p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <input
          placeholder="Product name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm"
        />
        <input
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm"
        />
        <input
          placeholder="Price"
          type="number"
          step="0.01"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm"
        />
        <input
          placeholder="Stock quantity"
          type="number"
          value={stock}
          onChange={(e) => setStock(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm"
        />
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}
      <button
        type="submit"
        disabled={saving}
        className="bg-blue-600 text-white rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
      >
        {saving ? "Saving…" : "Add product"}
      </button>
    </form>
  );
}

function OrdersTab({ shopId }: { shopId: string }) {
  const [orders, setOrders] = useState<DashboardOrder[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const data: DashboardOrder[] = await apiFetch(`/dashboard/orders?shop_id=${shopId}`);
    setOrders(data);
    setLoading(false);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  async function updateStatus(orderId: string, status: string) {
    await apiFetch(`/dashboard/orders/${orderId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    load();
  }

  if (loading) return <p className="text-sm text-gray-400 pt-4">Loading orders…</p>;
  if (orders.length === 0) return <p className="text-sm text-gray-400 pt-4">No orders yet.</p>;

  return (
    <div className="space-y-3 pt-4">
      {orders.map((o) => (
        <div key={o.id} className="border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Order #{o.id.slice(0, 8)}</p>
            <p className="text-sm font-semibold">₹{o.total_amount}</p>
          </div>
          <p className="text-xs text-gray-500">{o.buyer_email}</p>
          <div className="flex items-center justify-between mt-2">
            <p className="text-xs text-gray-500 capitalize">{o.status.replace("_", " ")}</p>
            <div className="flex gap-2">
              {(STATUS_TRANSITIONS[o.status] ?? []).map((next) => (
                <button
                  key={next}
                  onClick={() => updateStatus(o.id, next)}
                  className="text-xs text-blue-600 underline capitalize"
                >
                  Mark {next}
                </button>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SummaryTab({ shopId }: { shopId: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/dashboard/summary")
      .then((data: Summary[]) => setSummary(data.find((s) => s.shop_id === shopId) ?? null))
      .finally(() => setLoading(false));
  }, [shopId]);

  if (loading) return <p className="text-sm text-gray-400 pt-4">Loading summary…</p>;
  if (!summary) return <p className="text-sm text-gray-400 pt-4">No data yet.</p>;

  return (
    <div className="grid grid-cols-2 gap-4 pt-4">
      <div className="border rounded-lg p-4">
        <p className="text-xs text-gray-500">Confirmed orders</p>
        <p className="text-2xl font-bold">{summary.confirmed_orders}</p>
      </div>
      <div className="border rounded-lg p-4">
        <p className="text-xs text-gray-500">Revenue</p>
        <p className="text-2xl font-bold">₹{summary.revenue}</p>
      </div>
    </div>
  );
}
