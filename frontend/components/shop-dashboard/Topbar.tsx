"use client";

import { MenuButton } from "@/components/dashboard/NavDrawer";
import { NotificationBell } from "@/components/notifications/NotificationBell";

export function Topbar({ title, name, onMenu }: { title: string; name: string | null; onMenu: () => void }) {
  const initials = (name ?? "?")
    .split(" ")
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-3 px-4 sm:px-8 py-3 sm:py-5 border-b border-gray-100 bg-white">
      <div className="flex items-center gap-2 min-w-0">
        <MenuButton onClick={onMenu} />
        <h1 className="text-lg sm:text-xl font-bold text-gray-900 truncate">{title}</h1>
      </div>
      <div className="flex items-center gap-4 shrink-0">
        <NotificationBell />
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-teal-500 text-white text-xs font-semibold flex items-center justify-center">
            {initials || "SO"}
          </div>
          <span className="text-sm font-medium text-gray-700 hidden sm:inline">{name ?? "Shop Owner"}</span>
        </div>
      </div>
    </header>
  );
}
