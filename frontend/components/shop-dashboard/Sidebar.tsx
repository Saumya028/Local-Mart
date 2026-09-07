"use client";

import { Shop } from "./types";

export type TabKey = "dashboard" | "orders" | "products" | "inventory" | "analytics";

const NAV: { key: TabKey; label: string; icon: JSX.Element }[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <rect x="2.5" y="2.5" width="6" height="6" rx="1.3" stroke="currentColor" strokeWidth="1.6" />
        <rect x="11.5" y="2.5" width="6" height="6" rx="1.3" stroke="currentColor" strokeWidth="1.6" />
        <rect x="2.5" y="11.5" width="6" height="6" rx="1.3" stroke="currentColor" strokeWidth="1.6" />
        <rect x="11.5" y="11.5" width="6" height="6" rx="1.3" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    key: "orders",
    label: "Orders",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <path d="M4 6h12l-1 10a1.5 1.5 0 0 1-1.5 1.35H6.5A1.5 1.5 0 0 1 5 16L4 6Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7 6V5a3 3 0 0 1 6 0v1" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    key: "products",
    label: "Products",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <path d="M3 6.5 10 3l7 3.5-7 3.5-7-3.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M3 6.5V14l7 3.5 7-3.5V6.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M10 10v7.5" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    key: "inventory",
    label: "Inventory",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <path d="M10 2 3 5.5v9L10 18l7-3.5v-9L10 2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M10 9.5v.01" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
        <path d="M10 9.5 3.3 5.9M10 9.5l6.7-3.6M10 9.5V17" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    key: "analytics",
    label: "Analytics",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <path d="M3.5 16.5V3.5M3.5 16.5h13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M6.5 14v-3M10 14V7M13.5 14V9.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
  },
];

export function Sidebar({
  shop,
  shops,
  onSelectShop,
  tab,
  onSelectTab,
  pendingCount,
}: {
  shop: Shop | null;
  shops: Shop[];
  onSelectShop: (id: string) => void;
  tab: TabKey;
  onSelectTab: (t: TabKey) => void;
  pendingCount: number;
}) {
  return (
    <aside className="w-60 shrink-0 border-r border-gray-100 bg-white flex flex-col h-full">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0">
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
            <path d="M10 2 2.5 6v8L10 18l7.5-4V6L10 2Z" stroke="white" strokeWidth="1.4" fill="white" fillOpacity={0.15} />
          </svg>
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold text-gray-900">LocalMart</p>
          <p className="text-[11px] text-gray-400">Shop Dashboard</p>
        </div>
      </div>

      <div className="mx-3 mb-3 rounded-xl border border-gray-100 bg-gray-50 px-3 py-2.5">
        {shops.length > 1 ? (
          <select
            value={shop?.id ?? ""}
            onChange={(e) => onSelectShop(e.target.value)}
            className="w-full bg-transparent text-sm font-semibold text-gray-800 outline-none"
          >
            {shops.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        ) : (
          <p className="text-sm font-semibold text-gray-800 truncate">{shop?.name}</p>
        )}
        <p className="text-[11px] text-emerald-600 flex items-center gap-1 mt-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
          {shop?.is_active ? "Open" : "Closed"}
        </p>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {NAV.map((item) => (
          <button
            key={item.key}
            onClick={() => onSelectTab(item.key)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              tab === item.key
                ? "bg-blue-50 text-blue-700 font-medium"
                : "text-gray-500 hover:bg-gray-50 hover:text-gray-700"
            }`}
          >
            {item.icon}
            <span className="flex-1 text-left">{item.label}</span>
            {item.key === "orders" && pendingCount > 0 && (
              <span className="bg-blue-600 text-white text-[11px] font-semibold rounded-full w-5 h-5 flex items-center justify-center">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </nav>
    </aside>
  );
}
