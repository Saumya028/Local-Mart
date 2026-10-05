"use client";

import { ReactNode, useEffect } from "react";

// Shared by the admin and shop-owner sidebars. From the `md` breakpoint up
// it's an ordinary static sidebar (exactly the old layout). Below `md` it
// becomes an off-canvas drawer that slides in over the page with a dimmed
// backdrop, opened by the hamburger button in each dashboard's Topbar.
export function NavDrawer({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    // If the window is widened past the drawer breakpoint while it's
    // open (rotating a tablet, resizing a desktop window), close it so
    // the page doesn't stay scroll-locked behind a now-static sidebar.
    const onResize = () => {
      if (window.innerWidth >= 768) onClose();
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onResize);
    };
  }, [open, onClose]);

  return (
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`md:hidden fixed inset-0 z-30 bg-black/40 transition-opacity ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 max-w-[85vw] overflow-y-auto border-r border-gray-100 bg-white flex flex-col transition-transform duration-200 md:sticky md:top-0 md:z-auto md:h-screen md:w-60 md:max-w-none md:shrink-0 md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {children}
      </aside>
    </>
  );
}

export function MenuButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Open menu"
      className="md:hidden -ml-1 p-2 rounded-lg text-gray-600 hover:bg-gray-100 shrink-0"
    >
      <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
        <path d="M3 5.5h14M3 10h14M3 14.5h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    </button>
  );
}
