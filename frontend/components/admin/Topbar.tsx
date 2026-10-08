"use client";

import { MenuButton } from "@/components/dashboard/NavDrawer";

export function Topbar({
  title,
  badgeCount,
  onMenu,
  search,
  onSearch,
  searchPlaceholder,
}: {
  title: string;
  badgeCount?: number;
  onMenu: () => void;
  // Omit searchPlaceholder on tabs with nothing to search (Dashboard,
  // Reports, Settings) and the box is hidden rather than left decorative.
  search?: string;
  onSearch?: (value: string) => void;
  searchPlaceholder?: string;
}) {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between px-4 sm:px-8 py-3 sm:py-5 border-b border-gray-100 bg-white gap-3 sm:gap-6">
      <div className="flex items-center gap-2 min-w-0">
        <MenuButton onClick={onMenu} />
        <h1 className="text-lg sm:text-xl font-bold text-gray-900 truncate">{title}</h1>
      </div>
      <div className="flex items-center gap-4 flex-1 justify-end">
        {searchPlaceholder && onSearch && (
        <div className="relative w-full max-w-xs hidden sm:block">
          <svg
            viewBox="0 0 20 20"
            fill="none"
            className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          >
            <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M16 16l-3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            value={search ?? ""}
            onChange={(e) => onSearch(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full bg-gray-50 border border-gray-100 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        )}
        <button aria-label="Notifications" className="relative text-gray-400 hover:text-gray-600 shrink-0">
          <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
            <path
              d="M5 8a5 5 0 0 1 10 0v3.2l1.3 2.3a.8.8 0 0 1-.7 1.2H4.4a.8.8 0 0 1-.7-1.2L5 11.2V8Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path d="M8.2 16.5a1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          {!!badgeCount && badgeCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500" />
          )}
        </button>
      </div>
    </header>
  );
}
