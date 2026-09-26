"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { setPostLoginRedirect } from "@/lib/postLoginRedirect";
import { Sidebar, TabKey } from "@/components/shop-dashboard/Sidebar";
import { Topbar } from "@/components/shop-dashboard/Topbar";
import { DashboardTab } from "@/components/shop-dashboard/DashboardTab";
import { OrdersTab } from "@/components/shop-dashboard/OrdersTab";
import { ReturnsTab } from "@/components/shop-dashboard/ReturnsTab";
import { ProductsTab } from "@/components/shop-dashboard/ProductsTab";
import { InventoryTab } from "@/components/shop-dashboard/InventoryTab";
import { AnalyticsTab } from "@/components/shop-dashboard/AnalyticsTab";
import { ShopStatusScreen } from "@/components/shop-dashboard/ShopStatusScreen";
import { DocumentUploader } from "@/components/shop-dashboard/DocumentUploader";
import { Shop } from "@/components/shop-dashboard/types";
import { UploadedDocument } from "@/lib/documentUpload";
import { useAttributeSchema } from "@/lib/attributeSchema";
import DynamicAttributeFields from "@/components/DynamicAttributeFields";

const TAB_TITLES: Record<TabKey, string> = {
  dashboard: "Dashboard",
  orders: "Orders",
  returns: "Returns",
  products: "Products",
  inventory: "Inventory",
  analytics: "Analytics",
};

export default function ShopDashboardPage() {
  const router = useRouter();
  const { profile, loading: authLoading, loggedIn, refresh } = useAuth();
  const [shops, setShops] = useState<Shop[]>([]);
  const [selectedShopId, setSelectedShopId] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("dashboard");
  const [loadingShops, setLoadingShops] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [pendingReturnsCount, setPendingReturnsCount] = useState(0);

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

  // Applying to sell is self-service (see POST /shops) — a guest just
  // needs to be signed in first, not turned away. setPostLoginRedirect
  // is the same mechanism the Login page's own shortcuts use: it records
  // where to land after a real sign-in succeeds, so a guest who clicks
  // "List Your Shop" goes login -> straight back here -> the apply form,
  // in one flow, instead of a dead-end "log in to continue" message.
  useEffect(() => {
    if (!authLoading && !loggedIn) {
      setPostLoginRedirect("/shop/dashboard");
      router.replace("/login");
    }
  }, [authLoading, loggedIn, router]);

  // After a successful application: pick up the fresh role (a plain
  // customer just became a shop_owner server-side, in the same
  // transaction as the shop row — see POST /shops) and load the shop
  // that was just created, so the page moves straight into showing its
  // pending-approval status instead of re-showing the apply form.
  async function handleShopApplied() {
    await refresh();
    setLoadingShops(true);
    await loadShops();
  }

  // Keep the "pending orders" badge in the sidebar fresh across tab
  // switches, so it stays accurate right after an order is Accepted
  // elsewhere in the UI without a full page reload.
  useEffect(() => {
    if (!selectedShopId) return;
    const shop = shops.find((s) => s.id === selectedShopId);
    if (shop?.approval_status !== "approved") return;
    let cancelled = false;
    apiFetch(`/dashboard/orders?shop_id=${selectedShopId}`)
      .then((orders: { status: string }[]) => {
        if (!cancelled) setPendingCount(orders.filter((o) => o.status === "confirmed").length);
      })
      .catch(() => {});
    apiFetch(`/dashboard/returns?shop_id=${selectedShopId}`)
      .then((returns: { status: string }[]) => {
        if (!cancelled) setPendingReturnsCount(returns.filter((r) => r.status === "requested").length);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedShopId, tab, shops]);

  if (authLoading || !loggedIn || (canSell && loadingShops)) {
    // Covers auth still resolving, AND the brief moment before the
    // effect above sends a guest on to /login — never a dead end.
    return (
      <main className="max-w-4xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  // Reaching here, the visitor is signed in. Selling is self-service: a
  // plain customer goes straight to the apply form, no separate
  // "request access" step first — submitting it is what makes them a
  // shop_owner (see POST /shops). The same form covers an
  // already-promoted account that just doesn't have a shop yet (e.g.
  // right after their first application, or an existing owner/admin
  // adding another shop).
  if (!canSell || shops.length === 0) {
    return (
      <main className="max-w-lg mx-auto px-6 py-10">
        <ApplyForm userId={profile!.id} onCreated={handleShopApplied} loadError={error} />
      </main>
    );
  }

  const selectedShop = shops.find((s) => s.id === selectedShopId) ?? null;

  // A shop that isn't approved yet gets NO dashboard functionality at
  // all, regardless of which nav tab is selected — see the backend's own
  // enforcement of this exact rule in shop_dashboard.py's
  // _require_approved_shop. This is the fix for the real gap a test run
  // found: previously this page rendered the full dashboard (add
  // products, etc.) for a shop that was still pending admin review.
  if (selectedShop && selectedShop.approval_status !== "approved") {
    return (
      <div className="flex min-h-screen bg-gray-50">
        <Sidebar
          shop={selectedShop}
          shops={shops}
          onSelectShop={setSelectedShopId}
          tab={tab}
          onSelectTab={setTab}
          pendingCount={0}
          pendingReturnsCount={0}
        />
        <div className="flex-1 overflow-y-auto">
          <ShopStatusScreen shop={selectedShop} userId={profile!.id} onUpdated={loadShops} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        shop={selectedShop}
        shops={shops}
        onSelectShop={setSelectedShopId}
        tab={tab}
        onSelectTab={setTab}
        pendingCount={pendingCount}
        pendingReturnsCount={pendingReturnsCount}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={TAB_TITLES[tab]} name={profile?.full_name ?? profile?.email ?? null} />
        <div className="flex-1 overflow-y-auto">
          {selectedShopId && tab === "dashboard" && (
            <DashboardTab shopId={selectedShopId} onGoToOrders={() => setTab("orders")} />
          )}
          {selectedShopId && tab === "orders" && <OrdersTab shopId={selectedShopId} />}
          {selectedShopId && tab === "returns" && <ReturnsTab shopId={selectedShopId} />}
          {selectedShopId && tab === "products" && <ProductsTab shopId={selectedShopId} userId={profile!.id} />}
          {selectedShopId && tab === "inventory" && <InventoryTab shopId={selectedShopId} />}
          {selectedShopId && tab === "analytics" && <AnalyticsTab shopId={selectedShopId} />}
        </div>
      </div>
    </div>
  );
}

function ApplyForm({
  userId,
  onCreated,
  loadError,
}: {
  userId: string;
  onCreated: () => void;
  loadError: string | null;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [addressLine1, setAddressLine1] = useState("");
  const [city, setCity] = useState("");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [attributes, setAttributes] = useState<Record<string, string | number | boolean>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { fields: attributeFields } = useAttributeSchema("shop", category);

  function handleAttributeChange(key: string, value: string | number | boolean) {
    setAttributes((prev) => ({ ...prev, [key]: value }));
  }

  // Customers can only find this shop in "near me" search once it has
  // coordinates on file (see GET /shops's lat/lng filter) — there's no
  // paid maps/geocoding API wired up, so the browser's own Geolocation
  // API is the simplest way to capture them: the applicant is standing
  // at (or near) the shop while filling this out.
  function useMyLocation() {
    if (!("geolocation" in navigator)) {
      setLocationError("Your browser doesn't support location access — enter the address manually.");
      return;
    }
    setLocating(true);
    setLocationError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
      },
      (err) => {
        setLocationError(
          err.code === err.PERMISSION_DENIED
            ? "Location access was denied — allow it in your browser settings, then try again."
            : "Couldn't get your location. Try again, or check your device's location settings."
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (documents.length === 0) {
      setError("Add at least one verification document before applying.");
      return;
    }
    if (!coords) {
      setError("Capture your shop's location before applying — it's how customers nearby will find you.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/shops", {
        method: "POST",
        body: JSON.stringify({
          name,
          category,
          documents,
          address_line1: addressLine1,
          city,
          latitude: coords.lat,
          longitude: coords.lng,
          attributes,
        }),
      });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Apply to sell on LocalMart</h1>
        <p className="text-sm text-gray-500 mt-1">
          Tell us about your shop and attach at least one verification document
          (e.g. a GST/business license or the owner&apos;s ID proof). An admin
          reviews every application before it goes live — you&apos;ll be able to
          manage products and orders here as soon as it&apos;s approved.
        </p>
      </div>

      <div className="space-y-3">
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
      </div>

      <div className="border-t border-gray-100 pt-4 space-y-3">
        <p className="text-sm font-medium text-gray-900">Shop location</p>
        <p className="text-xs text-gray-500 -mt-1">
          This is how customers nearby will find you — only shops within delivery range of a
          customer show up in their search.
        </p>
        <input
          placeholder="Shop address"
          value={addressLine1}
          onChange={(e) => setAddressLine1(e.target.value)}
          required
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          placeholder="City"
          value={city}
          onChange={(e) => setCity(e.target.value)}
          required
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={useMyLocation}
            disabled={locating}
            className="text-sm font-medium text-blue-600 border border-blue-200 rounded-md px-3 py-2 hover:bg-blue-50 disabled:opacity-50"
          >
            {locating ? "Locating…" : coords ? "Update location" : "Use my current location"}
          </button>
          {coords && (
            <span className="text-xs text-emerald-600">
              ✓ Location captured ({coords.lat.toFixed(4)}, {coords.lng.toFixed(4)})
            </span>
          )}
        </div>
        {locationError && <p className="text-xs text-red-500">{locationError}</p>}
      </div>

      {attributeFields.length > 0 && (
        <div className="border-t border-gray-100 pt-4">
          <DynamicAttributeFields fields={attributeFields} values={attributes} onChange={handleAttributeChange} />
        </div>
      )}

      <div className="border-t border-gray-100 pt-4">
        <p className="text-sm font-medium text-gray-900 mb-2">Verification documents</p>
        <DocumentUploader userId={userId} documents={documents} onChange={setDocuments} />
      </div>

      {(error || loadError) && <p className="text-sm text-red-500">{error || loadError}</p>}
      <button
        type="submit"
        disabled={saving}
        className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50"
      >
        {saving ? "Submitting…" : "Submit application"}
      </button>
    </form>
  );
}
