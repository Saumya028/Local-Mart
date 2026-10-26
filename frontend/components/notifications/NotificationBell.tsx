"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { timeAgo } from "@/components/shop-dashboard/types";
import type { AppNotification, NotificationList } from "./types";

const POLL_MS = 30_000;

/**
 * The bell: unread badge + a dropdown of the signed-in user's notifications
 * (order updates for customers; new orders, payments to confirm and returns
 * for shops). Used in the customer Header and the shop-dashboard Topbar.
 *
 * It polls the cheap /notifications/unread-count endpoint every 30s while
 * the tab is visible (and immediately when the tab becomes visible again) —
 * no websocket needed. The list itself is only fetched when the panel opens.
 */
export function NotificationBell({ className = "" }: { className?: string }) {
  const { loggedIn } = useAuth();
  const router = useRouter();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(async () => {
    try {
      const data: { unread_count: number } = await apiFetch("/notifications/unread-count");
      setUnread(data.unread_count);
    } catch {
      // A failed poll just keeps the last known count; never interrupt the page for it.
    }
  }, []);

  useEffect(() => {
    if (!loggedIn) return;
    refreshCount();
    const tick = () => {
      if (document.visibilityState === "visible") refreshCount();
    };
    const id = window.setInterval(tick, POLL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [loggedIn, refreshCount]);

  async function loadList(before?: string | null) {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ limit: "15" });
      if (before) qs.set("before", before);
      const data: NotificationList = await apiFetch(`/notifications?${qs.toString()}`);
      setItems((prev) => (before ? [...prev, ...data.items] : data.items));
      setNextBefore(data.next_before);
      setUnread(data.unread_count);
    } catch {
      setError("Couldn’t load notifications.");
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) loadList();
  }

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function openItem(n: AppNotification) {
    setOpen(false);
    if (!n.read_at) {
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
      setUnread((u) => Math.max(0, u - 1));
      apiFetch(`/notifications/${n.id}/read`, { method: "POST" }).catch(() => refreshCount());
    }
    if (n.link) router.push(n.link);
  }

  async function markAllRead() {
    setItems((prev) => prev.map((x) => ({ ...x, read_at: x.read_at ?? new Date().toISOString() })));
    setUnread(0);
    try {
      await apiFetch("/notifications/read-all", { method: "POST" });
    } catch {
      refreshCount();
    }
  }

  if (!loggedIn) return null;

  return (
    <div ref={wrapRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={toggle}
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="relative text-gray-500 hover:text-gray-800 p-1"
      >
        <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5" aria-hidden="true">
          <path
            d="M5 8a5 5 0 0 1 10 0v3.2l1.3 2.3a.8.8 0 0 1-.7 1.2H4.4a.8.8 0 0 1-.7-1.2L5 11.2V8Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path d="M8.2 16.5a1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold leading-[1.1rem] text-center">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="fixed inset-x-3 top-16 sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-96 z-50 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900">Notifications</p>
            {unread > 0 && (
              <button onClick={markAllRead} className="text-xs text-blue-600 hover:underline">
                Mark all as read
              </button>
            )}
          </div>

          <div className="max-h-[60vh] overflow-y-auto">
            {items.length === 0 && !loading && !error && (
              <p className="text-sm text-gray-400 px-4 py-8 text-center">You’re all caught up.</p>
            )}
            {items.map((n) => (
              <button
                key={n.id}
                onClick={() => openItem(n)}
                className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 flex gap-3 ${
                  n.read_at ? "" : "bg-blue-50/40"
                }`}
              >
                <span
                  className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${n.read_at ? "bg-transparent" : "bg-blue-500"}`}
                  aria-hidden="true"
                />
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-gray-900">{n.title}</span>
                  <span className="block text-xs text-gray-500 mt-0.5 line-clamp-3">{n.body}</span>
                  <span className="block text-[11px] text-gray-400 mt-1">{timeAgo(n.created_at)}</span>
                </span>
              </button>
            ))}
            {loading && <p className="text-xs text-gray-400 px-4 py-3">Loading…</p>}
            {error && <p className="text-xs text-red-500 px-4 py-3">{error}</p>}
            {nextBefore && !loading && (
              <button onClick={() => loadList(nextBefore)} className="w-full text-xs text-blue-600 hover:underline py-3">
                Show older
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
