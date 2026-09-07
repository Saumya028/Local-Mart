"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar, TabKey } from "@/components/shop-dashboard/Sidebar";
import { Topbar } from "@/components/shop-dashboard/Topbar";
import { DashboardTab } from "@/components/shop-dashboard/DashboardTab";
import { OrdersTab } from "@/components/shop-dashboard/OrdersTab";
import { ProductsTab } from "@/components/shop-dashboard/ProductsTab";
import { InventoryTab } from "@/components/shop-dashboard/InventoryTab";
import { AnalyticsTab } from "@/components/shop-dashboard/AnalyticsTab";
import { Shop } from "@/components/shop-dashboard/types";

const TAB_TITLES: Record<TabKey, string> = {
  dashboard: "Dashboard",
  orders: "Orders",
  products: "Products",
  inventory: "Inventory",
  analytics: "Analytics",
};

export default function ShopDashboardPage() {
  const { profile, loading: authLoading, loggedIn } = useAuth();
  const [shops, setShops] = useState<Shop[]>([]);
  const [selectedShopId, setSelectedShopId] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [loadingShops, setLoadingShops] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);

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
  }, [canSell, authLoading]);

  // Keep the "pending orders" badge in the sidebar fresh across tab
  // switches, so it stays accurate right after an order is Accepted
  // elsewhere in the UI without a full page reload.
  useEffect(() => {
    if (!selectedShopId) return;
    let cancelled = false;
    apiFetch(`/dashboard/orders?shop_id=${selectedShopId}`)
      .then((orders: { status: string }[]) => {
        if (!cancelled) setPendingCount(orders.filter((o) => o.status === "confirmed").length);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedShopId, tab]);

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

  const selectedShop = shops.find((s) => s.id === selectedShopId) ?? null;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        shop={selectedShop}
        shops={shops}
        onSelectShop={setSelectedShopId}
        tab={tab}
        onSelectTab={setTab}
        pendingCount={pendingCount}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={TAB_TITLES[tab]} name={profile?.full_name ?? profile?.email ?? null} />
        <div className="flex-1 overflow-y-auto">
          {selectedShopId && tab === "dashboard" && (
            <DashboardTab shopId={selectedShopId} onGoToOrders={() => setTab("orders")} />
          )}
          {selectedShopId && tab === "orders" && <OrdersTab shopId={selectedShopId} />}
          {selectedShopId && tab === "products" && <ProductsTab shopId={selectedShopId} />}
          {selectedShopId && tab === "inventory" && <InventoryTab shopId={selectedShopId} />}
          {selectedShopId && tab === "analytics" && <AnalyticsTab shopId={selectedShopId} />}
        </div>
      </div>
    </div>
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
