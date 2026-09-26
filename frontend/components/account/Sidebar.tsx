"use client";

import { AccountProfile, initials } from "./types";

export type AccountTabKey =
  | "orders"
  | "returns"
  | "wishlist"
  | "addresses"
  | "payments"
  | "reviews"
  | "settings"
  | "notifications";

const NAV: { key: AccountTabKey; label: string; icon: string }[] = [
  { key: "orders", label: "My Orders", icon: "📦" },
  { key: "returns", label: "My Returns", icon: "↩" },
  { key: "wishlist", label: "Wishlist", icon: "♡" },
  { key: "addresses", label: "Addresses", icon: "📍" },
  { key: "payments", label: "Saved Payments", icon: "💳" },
  { key: "reviews", label: "My Reviews", icon: "★" },
  { key: "settings", label: "Settings", icon: "⚙" },
  { key: "notifications", label: "Notifications", icon: "🔔" },
];

export function AccountSidebar({
  profile,
  orderCount,
  wishlistCount,
  tab,
  onSelectTab,
  onLogout,
}: {
  profile: AccountProfile;
  orderCount: number;
  wishlistCount: number;
  tab: AccountTabKey;
  onSelectTab: (t: AccountTabKey) => void;
  onLogout: () => void;
}) {
  return (
    <aside className="w-full sm:w-72 shrink-0 space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-6 text-center">
        <div className="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-blue-500 to-emerald-400 text-white flex items-center justify-center text-lg font-semibold">
          {initials(profile.full_name, profile.email, profile.phone)}
        </div>
        <p className="font-semibold text-gray-900 mt-3">{profile.full_name ?? profile.email ?? profile.phone ?? "Your account"}</p>
        {profile.email && <p className="text-sm text-gray-500">{profile.email}</p>}
        {profile.phone && <p className="text-sm text-gray-500">{profile.phone}</p>}

        <div className="grid grid-cols-2 gap-2 border-t border-gray-100 mt-4 pt-4">
          <div>
            <p className="text-lg font-bold text-gray-900">{orderCount}</p>
            <p className="text-xs text-gray-400">Orders</p>
          </div>
          <div>
            <p className="text-lg font-bold text-gray-900">{wishlistCount}</p>
            <p className="text-xs text-gray-400">Wishlist</p>
          </div>
        </div>
      </div>

      <nav className="bg-white rounded-2xl border border-gray-100 p-2">
        {NAV.map((item) => (
          <button
            key={item.key}
            onClick={() => onSelectTab(item.key)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-left transition-colors ${
              tab === item.key ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            <span className="w-4 text-center">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            <span className="text-gray-300">›</span>
          </button>
        ))}
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-left text-red-600 hover:bg-red-50 mt-1"
        >
          <span className="w-4 text-center">⎋</span>
          Log Out
        </button>
      </nav>
    </aside>
  );
}
