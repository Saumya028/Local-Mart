"use client";

export function Topbar({ title, name }: { title: string; name: string | null }) {
  const initials = (name ?? "?")
    .split(" ")
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="flex items-center justify-between px-8 py-5 border-b border-gray-100 bg-white">
      <h1 className="text-xl font-bold text-gray-900">{title}</h1>
      <div className="flex items-center gap-4">
        <button aria-label="Notifications" className="relative text-gray-400 hover:text-gray-600">
          <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
            <path
              d="M5 8a5 5 0 0 1 10 0v3.2l1.3 2.3a.8.8 0 0 1-.7 1.2H4.4a.8.8 0 0 1-.7-1.2L5 11.2V8Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path d="M8.2 16.5a1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500" />
        </button>
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
