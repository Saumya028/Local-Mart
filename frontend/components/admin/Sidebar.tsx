"use client";

export type AdminTabKey = "dashboard" | "shops" | "users" | "attributes" | "reports" | "settings";

const NAV: { key: AdminTabKey; label: string; icon: JSX.Element }[] = [
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
    key: "shops",
    label: "Manage Shops",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <path d="M3 7.5 4 3h12l1 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M3 7.5a1.8 1.8 0 0 0 3.6 0 1.8 1.8 0 0 0 3.6 0 1.8 1.8 0 0 0 3.6 0 1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M4 8.2V17h12V8.2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M8 17v-4.5h4V17" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    key: "users",
    label: "Manage Users",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <circle cx="7.2" cy="6.5" r="2.5" stroke="currentColor" strokeWidth="1.6" />
        <path d="M2.5 16.5c0-2.6 2.1-4.3 4.7-4.3s4.7 1.7 4.7 4.3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="14" cy="6.5" r="2" stroke="currentColor" strokeWidth="1.4" />
        <path d="M12.8 12.4c2 .2 3.7 1.8 3.7 4.1" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    key: "attributes",
    label: "Attributes",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <rect x="2.5" y="3.5" width="15" height="3.4" rx="1" stroke="currentColor" strokeWidth="1.6" />
        <rect x="2.5" y="8.6" width="15" height="3.4" rx="1" stroke="currentColor" strokeWidth="1.6" />
        <rect x="2.5" y="13.7" width="9" height="3.4" rx="1" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    key: "reports",
    label: "Reports",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <path d="M5.5 2.5h6l3 3v12h-9v-15Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7.3 10v3M10 8.3V13M12.7 11.3V13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    key: "settings",
    label: "Settings",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <circle cx="10" cy="10" r="2.6" stroke="currentColor" strokeWidth="1.6" />
        <path
          d="M10 3.3v1.5M10 15.2v1.5M16.7 10h-1.5M4.8 10H3.3M14.7 5.3l-1 1M6.3 13.7l-1 1M14.7 14.7l-1-1M6.3 6.3l-1-1"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
];

export function Sidebar({
  tab,
  onSelectTab,
  pendingShopsCount,
  adminEmail,
}: {
  tab: AdminTabKey;
  onSelectTab: (t: AdminTabKey) => void;
  pendingShopsCount: number;
  adminEmail: string | null;
}) {
  return (
    <aside className="w-60 shrink-0 border-r border-gray-100 bg-white flex flex-col h-full">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0">
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
            <path
              d="M10 2 2.5 6v8L10 18l7.5-4V6L10 2Z"
              stroke="white"
              strokeWidth="1.4"
              fill="white"
              fillOpacity={0.15}
            />
          </svg>
        </div>
        <div className="leading-tight">
          <p className="text-sm font-bold text-gray-900">LocalMart</p>
          <p className="text-[11px] text-gray-400">Admin Panel</p>
        </div>
      </div>

      <div className="mx-3 mb-3 rounded-xl border border-gray-100 bg-gray-50 px-3 py-2.5 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-full bg-violet-500 text-white text-xs font-semibold flex items-center justify-center shrink-0">
          SA
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-800 truncate">Super Admin</p>
          <p className="text-[11px] text-gray-400 truncate">{adminEmail ?? "admin@localmart.in"}</p>
        </div>
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
            {item.key === "shops" && pendingShopsCount > 0 && (
              <span className="bg-red-500 text-white text-[11px] font-semibold rounded-full w-5 h-5 flex items-center justify-center">
                {pendingShopsCount}
              </span>
            )}
          </button>
        ))}
      </nav>
    </aside>
  );
}
