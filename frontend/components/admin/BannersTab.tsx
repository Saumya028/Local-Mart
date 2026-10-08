"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { AdminBanner, AdminBanners, AdminBannerState, formatINR, matchesSearch, timeAgo } from "./types";

const STATE_META: Record<AdminBannerState, { label: string; cls: string }> = {
  pending: { label: "Needs review", cls: "bg-amber-50 text-amber-700" },
  awaiting_payment: { label: "Approved · awaiting payment", cls: "bg-blue-50 text-blue-600" },
  live: { label: "Live", cls: "bg-emerald-50 text-emerald-600" },
  expired: { label: "Ended", cls: "bg-gray-100 text-gray-500" },
  rejected: { label: "Rejected", cls: "bg-red-50 text-red-600" },
};

const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-IN") : "—");

// Admin side of banners: review artwork, approve/reject, and see what is
// live. Shop owners buy and renew from their own dashboard — nothing here
// grants space for free; approval just unlocks payment.
export function BannersTab({ search = "" }: { search?: string }) {
  const [data, setData] = useState<AdminBanners | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);

  async function load() {
    try {
      setData(await apiFetch("/admin/banners"));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function act(b: AdminBanner, action: "approve" | "reject" | "takedown", body?: object) {
    setActingId(b.id);
    try {
      await apiFetch(`/admin/banners/${b.id}/${action}`, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActingId(null);
    }
  }

  function reject(b: AdminBanner) {
    const reason = window.prompt(`Why is this banner from "${b.shop_name}" being rejected? (shown to the shop)`);
    if (reason === null) return;
    if (reason.trim().length < 3) {
      setError("Please give a short reason.");
      return;
    }
    act(b, "reject", { reason: reason.trim() });
  }

  function takedown(b: AdminBanner) {
    if (!window.confirm(`Take "${b.shop_name}"'s live banner down now? This does not refund them.`)) return;
    act(b, "takedown");
  }

  if (!data) {
    return (
      <div className="p-4 sm:p-6 lg:p-8">
        {error ? <p className="text-sm text-red-500 break-words">{error}</p> : <p className="text-sm text-gray-400">Loading…</p>}
      </div>
    );
  }

  const shown = data.banners.filter((b) => matchesSearch(search, b.shop_name, b.owner_email, b.slot_name, b.title));
  const needsReview = shown.filter((b) => b.state === "pending");
  const rest = shown.filter((b) => b.state !== "pending");

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-5">
      {error && <p className="text-sm text-red-500 break-words">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <p className="text-xs text-gray-400">Waiting for review</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{data.pending_count}</p>
        </div>
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <p className="text-xs text-gray-400">Live right now</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{data.live_count}</p>
        </div>
        <div className="bg-white rounded-2xl border border-gray-100 p-5">
          <p className="text-xs text-gray-400">Banner revenue</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{formatINR(data.revenue)}</p>
        </div>
      </div>

      {needsReview.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-900">Needs review</h3>
          {needsReview.map((b) => (
            <div key={b.id} className="bg-white rounded-2xl border border-gray-100 p-4 flex flex-col lg:flex-row gap-4">
              <div
                className="relative w-full lg:w-96 shrink-0 overflow-hidden rounded-lg bg-gray-50"
                style={{ aspectRatio: `${b.width} / ${b.height}` }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- advertiser-uploaded Supabase Storage URL */}
                <img src={b.image_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                <p className="text-sm font-semibold text-gray-900">{b.shop_name}</p>
                <p className="text-xs text-gray-400">
                  {b.owner_email} · requested {timeAgo(b.created_at)}
                </p>
                <p className="text-xs text-gray-600">
                  {b.slot_name} · {b.width}×{b.height}px · {formatINR(b.price)} for {b.duration_days} days
                </p>
                {b.title && <p className="text-xs text-gray-500">&ldquo;{b.title}&rdquo;</p>}
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={() => act(b, "approve")}
                    disabled={actingId === b.id}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium rounded-lg px-3 py-1.5 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => reject(b)}
                    disabled={actingId === b.id}
                    className="text-xs font-medium text-red-600 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-50 disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-900">All banners</h3>
        {rest.length === 0 ? (
          <p className="text-sm text-gray-400">
            {search.trim() ? "No banners match your search." : "No banners yet — shop owners request them from their dashboard."}
          </p>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-100 overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                  <th className="px-5 py-3 font-medium">Banner</th>
                  <th className="px-5 py-3 font-medium">Shop</th>
                  <th className="px-5 py-3 font-medium">Spot</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Runs until</th>
                  <th className="px-5 py-3 font-medium">Views / clicks</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rest.map((b) => {
                  const meta = STATE_META[b.state];
                  return (
                    <tr key={b.id} className="border-b border-gray-50 last:border-0">
                      <td className="px-5 py-3">
                        {/* eslint-disable-next-line @next/next/no-img-element -- advertiser-uploaded Supabase Storage URL */}
                        <img src={b.image_url} alt="" className="w-24 rounded object-cover" style={{ aspectRatio: `${b.width} / ${b.height}` }} />
                      </td>
                      <td className="px-5 py-3 font-medium text-gray-900">
                        {b.shop_name}
                        <span className="block text-xs font-normal text-gray-400">{b.owner_email}</span>
                      </td>
                      <td className="px-5 py-3 text-gray-500">{b.slot_name}</td>
                      <td className="px-5 py-3">
                        <span className={`text-xs font-medium rounded-full px-2.5 py-1 ${meta.cls}`}>{meta.label}</span>
                        {b.state === "rejected" && b.rejection_reason && (
                          <span className="block text-xs text-gray-400 mt-1">{b.rejection_reason}</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-gray-500">{fmt(b.ends_at)}</td>
                      <td className="px-5 py-3 text-gray-500">
                        {b.impressions.toLocaleString("en-IN")} / {b.clicks.toLocaleString("en-IN")}
                      </td>
                      <td className="px-5 py-3 text-right space-x-3">
                        {b.state === "awaiting_payment" && (
                          <button
                            onClick={() => reject(b)}
                            disabled={actingId === b.id}
                            className="text-xs text-red-600 hover:underline disabled:opacity-50"
                          >
                            Reject
                          </button>
                        )}
                        {b.state === "live" && (
                          <button
                            onClick={() => takedown(b)}
                            disabled={actingId === b.id}
                            className="text-xs text-gray-500 hover:underline disabled:opacity-50"
                          >
                            Take down
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
