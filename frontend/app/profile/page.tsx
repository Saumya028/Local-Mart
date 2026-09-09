"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabaseClient";
import { useAuth } from "@/contexts/AuthContext";
import { AccountSidebar, AccountTabKey } from "@/components/account/Sidebar";
import { OrdersTab } from "@/components/account/OrdersTab";
import { WishlistTab } from "@/components/account/WishlistTab";
import { AddressesTab } from "@/components/account/AddressesTab";
import { SettingsTab } from "@/components/account/SettingsTab";
import { ComingSoonTab } from "@/components/account/ComingSoonTab";

const TAB_TITLES: Record<AccountTabKey, string> = {
  orders: "My Orders",
  wishlist: "Wishlist",
  addresses: "Addresses",
  payments: "Saved Payments",
  reviews: "My Reviews",
  settings: "Settings",
  notifications: "Notifications",
};

export default function ProfilePage() {
  const { profile, loading: authLoading, loggedIn, refresh } = useAuth();
  const [tab, setTab] = useState<AccountTabKey>("orders");
  const [orderCount, setOrderCount] = useState(0);
  const [wishlistCount, setWishlistCount] = useState(0);

  async function handleLogout() {
    await supabase.auth.signOut();
    // Full reload, same reasoning as AuthStatus.tsx's handleLogout: this
    // guarantees every component's in-memory state (not just
    // AuthContext) resets on logout, which matters more on a page this
    // stateful (orders/wishlist/addresses all cached in local state).
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/";
  }

  if (authLoading) {
    return (
      <main className="max-w-5xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  if (!loggedIn || !profile) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 space-y-3">
        <h1 className="text-2xl font-bold">My Account</h1>
        <p className="text-sm text-gray-500">Log in to see your account.</p>
      </main>
    );
  }

  return (
    <main className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-center gap-2 mb-6">
        <h1 className="text-xl font-bold text-gray-900">My Account</h1>
      </div>

      <div className="flex flex-col sm:flex-row gap-6">
        <AccountSidebar
          profile={profile}
          orderCount={orderCount}
          wishlistCount={wishlistCount}
          tab={tab}
          onSelectTab={setTab}
          onLogout={handleLogout}
        />

        <div className="flex-1 min-w-0 space-y-4">
          <h2 className="text-lg font-bold text-gray-900">{TAB_TITLES[tab]}</h2>

          {tab === "orders" && <OrdersTab onOrdersLoaded={(orders) => setOrderCount(orders.length)} />}
          {tab === "wishlist" && <WishlistTab onLoaded={(items) => setWishlistCount(items.length)} />}
          {tab === "addresses" && <AddressesTab />}
          {tab === "settings" && <SettingsTab profile={profile} onUpdated={() => refresh()} />}
          {tab === "payments" && (
            <ComingSoonTab
              title="No saved payment methods"
              description="LocalMart doesn't store your card details — payments go straight through Razorpay at checkout, which is deliberately more secure than a marketplace keeping card numbers on file."
            />
          )}
          {tab === "reviews" && (
            <ComingSoonTab
              title="Reviews are coming soon"
              description="Product and shop reviews aren't built yet — this tab will show reviews you've left once that feature ships."
            />
          )}
          {tab === "notifications" && (
            <ComingSoonTab
              title="Notifications are coming soon"
              description="Order status updates and alerts aren't wired up yet — for now, check My Orders for the latest status."
            />
          )}
        </div>
      </div>
    </main>
  );
}
