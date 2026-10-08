"use client";

import { useCallback, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar, AdminTabKey } from "@/components/admin/Sidebar";
import { Topbar } from "@/components/admin/Topbar";
import { DashboardTab } from "@/components/admin/DashboardTab";
import { ShopsTab } from "@/components/admin/ShopsTab";
import { UsersTab } from "@/components/admin/UsersTab";
import { BannersTab } from "@/components/admin/BannersTab";
import { AttributesTab } from "@/components/admin/AttributesTab";
import { ReportsTab } from "@/components/admin/ReportsTab";
import { SettingsTab } from "@/components/admin/SettingsTab";

// Tabs whose list the top-bar search box filters (others hide the box).
const SEARCH_PLACEHOLDERS: Partial<Record<AdminTabKey, string>> = {
  shops: "Search shops, owners, categories…",
  banners: "Search shops or banner spots…",
  users: "Search name, email or role…",
  attributes: "Search categories…",
};

const TAB_TITLES: Record<AdminTabKey, string> = {
  dashboard: "Dashboard",
  shops: "Shops",
  banners: "Banners",
  users: "Users",
  attributes: "Attributes",
  reports: "Reports",
  settings: "Settings",
};

export default function AdminPanelPage() {
  const { profile, loading: authLoading, loggedIn } = useAuth();
  const [tab, setTab] = useState<AdminTabKey>("dashboard");
  const [pendingShopsCount, setPendingShopsCount] = useState(0);
  const [search, setSearch] = useState("");
  // Mobile nav drawer (the sidebar is off-canvas below the `md` breakpoint).
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  const isAdmin = profile?.role === "admin";

  if (authLoading) {
    return (
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  if (!loggedIn) {
    return (
      <main className="max-w-md mx-auto px-4 sm:px-6 py-8 sm:py-10 space-y-3">
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-sm text-gray-500">Log in to continue.</p>
      </main>
    );
  }

  // Same pattern as the Shop Dashboard: the frontend never even attempts
  // a role-gated request unless it already knows the role allows it —
  // the backend enforces this independently on every /admin/* endpoint
  // via require_role("admin"), so this check is a UX nicety, not the
  // real security boundary.
  if (!isAdmin) {
    return (
      <main className="max-w-md mx-auto px-4 sm:px-6 py-8 sm:py-10 space-y-3">
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-sm text-gray-500">
          This area is restricted to platform admins. If you believe your
          account should have access, contact an existing admin.
        </p>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        tab={tab}
        onSelectTab={(t) => {
          setTab(t);
          setSearch("");
        }}
        pendingShopsCount={pendingShopsCount}
        adminEmail={profile?.email ?? null}
        open={menuOpen}
        onClose={closeMenu}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          title={TAB_TITLES[tab]}
          badgeCount={pendingShopsCount}
          onMenu={() => setMenuOpen(true)}
          search={search}
          onSearch={setSearch}
          searchPlaceholder={SEARCH_PLACEHOLDERS[tab]}
        />
        <div className="flex-1 min-w-0">
          {tab === "dashboard" && <DashboardTab onGoToShops={() => setTab("shops")} />}
          {tab === "shops" && <ShopsTab search={search} onPendingCountChange={setPendingShopsCount} />}
          {tab === "banners" && <BannersTab search={search} />}
          {tab === "users" && <UsersTab search={search} selfId={profile?.id ?? null} />}
          {tab === "attributes" && <AttributesTab search={search} />}
          {tab === "reports" && <ReportsTab />}
          {tab === "settings" && <SettingsTab />}
        </div>
      </div>
    </div>
  );
}
