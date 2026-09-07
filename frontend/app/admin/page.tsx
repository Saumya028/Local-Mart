"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar, AdminTabKey } from "@/components/admin/Sidebar";
import { Topbar } from "@/components/admin/Topbar";
import { DashboardTab } from "@/components/admin/DashboardTab";
import { ShopsTab } from "@/components/admin/ShopsTab";
import { UsersTab } from "@/components/admin/UsersTab";
import { ReportsTab } from "@/components/admin/ReportsTab";
import { SettingsTab } from "@/components/admin/SettingsTab";

const TAB_TITLES: Record<AdminTabKey, string> = {
  dashboard: "Dashboard",
  shops: "Shops",
  users: "Users",
  reports: "Reports",
  settings: "Settings",
};

export default function AdminPanelPage() {
  const { profile, loading: authLoading, loggedIn } = useAuth();
  const [tab, setTab] = useState<AdminTabKey>("dashboard");
  const [pendingShopsCount, setPendingShopsCount] = useState(0);

  const isAdmin = profile?.role === "admin";

  if (authLoading) {
    return (
      <main className="max-w-5xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  if (!loggedIn) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 space-y-3">
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
      <main className="max-w-md mx-auto px-6 py-10 space-y-3">
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
        onSelectTab={setTab}
        pendingShopsCount={pendingShopsCount}
        adminEmail={profile?.email ?? null}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={TAB_TITLES[tab]} badgeCount={pendingShopsCount} />
        <div className="flex-1 overflow-y-auto">
          {tab === "dashboard" && <DashboardTab onGoToShops={() => setTab("shops")} />}
          {tab === "shops" && <ShopsTab onPendingCountChange={setPendingShopsCount} />}
          {tab === "users" && <UsersTab selfId={profile?.id ?? null} />}
          {tab === "reports" && <ReportsTab />}
          {tab === "settings" && <SettingsTab />}
        </div>
      </div>
    </div>
  );
}
