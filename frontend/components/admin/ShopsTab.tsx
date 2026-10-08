"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { AdminShop, AdminSponsorships, formatINR, matchesSearch, timeAgo, docsStatusMeta } from "./types";

type SubTab = "pending" | "all" | "sponsorships";

export function ShopsTab({
  search = "",
  onPendingCountChange,
}: {
  search?: string;
  onPendingCountChange?: (n: number) => void;
}) {
  const [subTab, setSubTab] = useState<SubTab>("pending");
  const [pendingShops, setPendingShops] = useState<AdminShop[]>([]);
  const [allShops, setAllShops] = useState<AdminShop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);
  const [sponsorships, setSponsorships] = useState<AdminSponsorships | null>(null);

  const shopMatches = (s: AdminShop) => matchesSearch(search, s.name, s.category, s.owner_name, s.owner_email, s.location);
  const shownPending = pendingShops.filter(shopMatches);
  const shownAll = allShops.filter(shopMatches);
  const shownPurchases = (sponsorships?.purchases ?? []).filter((p) =>
    matchesSearch(search, p.shop_name, p.owner_email, p.plan_name)
  );

  async function load() {
    setLoading(true);
    try {
      const [pending, all, spons] = await Promise.all([
        apiFetch("/admin/shops?approval_status=pending"),
        apiFetch("/admin/shops"),
        apiFetch("/admin/sponsorships"),
      ]);
      setPendingShops(pending);
      setAllShops(all);
      setSponsorships(spons);
      onPendingCountChange?.(pending.length);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function act(shop: AdminShop, action: "approve" | "reject" | "request-docs") {
    let reason: string | null = null;
    if (action === "reject") {
      reason = window.prompt(`Reason for rejecting "${shop.name}"? (shown to the owner, optional)`) ?? null;
      if (reason === null) return; // user hit Cancel — don't reject
    } else if (action === "request-docs") {
      reason = window.prompt(`What documents does "${shop.name}" still need? (shown to the owner)`) ?? null;
      if (reason === null) return;
    }

    setActingId(shop.id);
    try {
      await apiFetch(`/admin/shops/${shop.id}/${action}`, {
        method: "PATCH",
        body: reason !== null ? JSON.stringify({ reason: reason || null }) : undefined,
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActingId(null);
    }
  }

  // Moderation only — sponsorship is BOUGHT by shop owners from their own
  // dashboard (Promote tab), never granted here.
  async function revokeSponsorship(shop: AdminShop) {
    if (!window.confirm(`End "${shop.name}"'s paid promotion now? This does not refund them.`)) return;
    setActingId(shop.id);
    try {
      await apiFetch(`/admin/shops/${shop.id}/sponsorship/revoke`, { method: "POST" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActingId(null);
    }
  }

  async function toggleActive(shop: AdminShop) {
    setActingId(shop.id);
    try {
      await apiFetch(`/admin/shops/${shop.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !shop.is_active }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActingId(null);
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-5">
      <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1 w-full sm:w-fit overflow-x-auto">
        <button
          onClick={() => setSubTab("pending")}
          className={`flex items-center justify-center gap-2 text-sm font-medium rounded-lg px-3 sm:px-4 py-2 transition-colors whitespace-nowrap flex-1 sm:flex-none ${
            subTab === "pending" ? "bg-white shadow-sm text-gray-900" : "text-gray-500"
          }`}
        >
          Pending Approval
          {pendingShops.length > 0 && (
            <span className="bg-amber-100 text-amber-700 text-xs font-semibold rounded-full px-2 py-0.5">
              {pendingShops.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setSubTab("all")}
          className={`text-sm font-medium rounded-lg px-3 sm:px-4 py-2 transition-colors whitespace-nowrap flex-1 sm:flex-none ${
            subTab === "all" ? "bg-white shadow-sm text-gray-900" : "text-gray-500"
          }`}
        >
          All Shops
        </button>
        <button
          onClick={() => setSubTab("sponsorships")}
          className={`text-sm font-medium rounded-lg px-3 sm:px-4 py-2 transition-colors whitespace-nowrap flex-1 sm:flex-none ${
            subTab === "sponsorships" ? "bg-white shadow-sm text-gray-900" : "text-gray-500"
          }`}
        >
          Sponsorships
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-400">Loading shops…</p>
      ) : subTab === "pending" ? (
        shownPending.length === 0 ? (
          <p className="text-sm text-gray-400">
            {search.trim() ? "No pending shops match your search." : "No shops waiting on approval."}
          </p>
        ) : (
          <div className="space-y-4">
            {shownPending.map((shop) => (
              <div key={shop.id} className="bg-white rounded-2xl border border-gray-100 p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
                    <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
                      <path d="M3 7.5 4 3h12l1 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
                      <path d="M4 8.2V17h12V8.2" stroke="currentColor" strokeWidth="1.6" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{shop.name}</p>
                    <p className="text-xs text-gray-400 truncate">
                      {shop.owner_name ?? shop.owner_email ?? "Shop owner"} · {shop.category}
                      {shop.location ? ` · ${shop.location}` : ""}
                    </p>
                    <p className="text-xs text-gray-300 mt-0.5">Applied {timeAgo(shop.created_at)}</p>
                    {shop.documents.length > 0 && (
                      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5">
                        {shop.documents.map((doc, i) => (
                          <a
                            key={`${doc.url}-${i}`}
                            href={doc.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-blue-600 hover:underline"
                          >
                            📄 {doc.name}
                          </a>
                        ))}
                      </div>
                    )}
                    {shop.rejection_reason && (
                      <p className="text-xs text-gray-400 mt-1 italic">Last note: {shop.rejection_reason}</p>
                    )}
                  </div>
                </div>
                <div className="flex flex-col lg:items-end gap-2 lg:shrink-0">
                  <span
                    className={`text-xs font-medium rounded-full px-2.5 py-1 whitespace-nowrap ${docsStatusMeta(shop.docs_status).className}`}
                  >
                    {docsStatusMeta(shop.docs_status).label}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => act(shop, "approve")}
                      disabled={actingId === shop.id}
                      className="text-xs font-medium bg-emerald-500 text-white rounded-lg px-3 py-1.5 hover:bg-emerald-600 disabled:opacity-50 whitespace-nowrap"
                    >
                      ✓ Approve Shop
                    </button>
                    <button
                      onClick={() => act(shop, "request-docs")}
                      disabled={actingId === shop.id}
                      className="text-xs font-medium border border-gray-200 text-gray-600 rounded-lg px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50 whitespace-nowrap"
                    >
                      ⚠ Request Docs
                    </button>
                    <button
                      onClick={() => act(shop, "reject")}
                      disabled={actingId === shop.id}
                      className="text-xs font-medium text-red-600 rounded-lg px-3 py-1.5 hover:bg-red-50 disabled:opacity-50"
                    >
                      ✕ Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      ) : subTab === "sponsorships" ? (
        sponsorships && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-white rounded-2xl border border-gray-100 p-5">
                <p className="text-xs text-gray-400">Sponsored right now</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {sponsorships.active_shops}
                  <span className="text-sm font-medium text-gray-400"> / {sponsorships.total_shops} shops</span>
                </p>
              </div>
              <div className="bg-white rounded-2xl border border-gray-100 p-5">
                <p className="text-xs text-gray-400">Purchases</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{sponsorships.paid_purchases}</p>
              </div>
              <div className="bg-white rounded-2xl border border-gray-100 p-5">
                <p className="text-xs text-gray-400">Sponsorship revenue</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{formatINR(sponsorships.revenue)}</p>
              </div>
            </div>
            {shownPurchases.length === 0 ? (
              <p className="text-sm text-gray-400">
                {search.trim() ? "No purchases match your search." : "No shop has bought a promotion yet."}
              </p>
            ) : (
              <div className="bg-white rounded-2xl border border-gray-100 overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                      <th className="px-5 py-3 font-medium">Shop</th>
                      <th className="px-5 py-3 font-medium">Plan</th>
                      <th className="px-5 py-3 font-medium">Amount</th>
                      <th className="px-5 py-3 font-medium">Paid on</th>
                      <th className="px-5 py-3 font-medium">Runs until</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shownPurchases.map((p) => (
                      <tr key={p.id} className="border-b border-gray-50 last:border-0">
                        <td className="px-5 py-3 font-medium text-gray-900">
                          {p.shop_name}
                          <span className="block text-xs font-normal text-gray-400">{p.owner_email}</span>
                        </td>
                        <td className="px-5 py-3 text-gray-500">{p.plan_name}</td>
                        <td className="px-5 py-3 text-gray-500">{formatINR(p.amount)}</td>
                        <td className="px-5 py-3 text-gray-500">
                          {p.paid_at ? new Date(p.paid_at).toLocaleDateString("en-IN") : "—"}
                        </td>
                        <td className="px-5 py-3 text-gray-500">
                          {p.ends_at ? new Date(p.ends_at).toLocaleDateString("en-IN") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      ) : shownAll.length === 0 ? (
        <p className="text-sm text-gray-400">{search.trim() ? "No shops match your search." : "No shops yet."}</p>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-100 overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                <th className="px-5 py-3 font-medium">Shop</th>
                <th className="px-5 py-3 font-medium">Category</th>
                <th className="px-5 py-3 font-medium">Owner</th>
                <th className="px-5 py-3 font-medium">Rating</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Sponsored</th>
                <th className="px-5 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {shownAll.map((shop) => (
                <tr key={shop.id} className="border-b border-gray-50 last:border-0">
                  <td className="px-5 py-3 font-medium text-gray-900">{shop.name}</td>
                  <td className="px-5 py-3 text-gray-500">{shop.category}</td>
                  <td className="px-5 py-3 text-gray-500">{shop.owner_name ?? shop.owner_email ?? "Shop owner"}</td>
                  <td className="px-5 py-3 text-gray-500">{shop.rating.toFixed(1)}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`text-xs font-medium rounded-full px-2.5 py-1 ${
                        shop.approval_status === "rejected"
                          ? "bg-red-50 text-red-600"
                          : shop.is_active
                          ? "bg-emerald-50 text-emerald-600"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {shop.approval_status === "rejected" ? "Rejected" : shop.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    {shop.is_sponsored ? (
                      <span className="text-xs font-medium rounded-full px-2.5 py-1 bg-amber-50 text-amber-700">
                        Active · until {new Date(shop.sponsored_until!).toLocaleDateString("en-IN")}
                      </span>
                    ) : shop.sponsored_until ? (
                      <span className="text-xs text-gray-400">
                        Expired {new Date(shop.sponsored_until).toLocaleDateString("en-IN")}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">Not purchased</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right space-x-3">
                    {shop.is_sponsored && (
                      <button
                        onClick={() => revokeSponsorship(shop)}
                        disabled={actingId === shop.id}
                        className="text-xs text-gray-500 hover:underline disabled:opacity-50"
                      >
                        End promotion
                      </button>
                    )}
                    {shop.approval_status === "approved" && (
                      <button
                        onClick={() => toggleActive(shop)}
                        disabled={actingId === shop.id}
                        className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                      >
                        {shop.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
