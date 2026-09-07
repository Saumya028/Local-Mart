"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { AdminUser, UsersSummary } from "./types";

const ROLES = ["customer", "shop_owner", "delivery_partner", "admin"] as const;

const ROLE_LABELS: Record<string, string> = {
  customer: "Customer",
  shop_owner: "Shop Owner",
  delivery_partner: "Delivery Partner",
  admin: "Admin",
};

const ROLE_BADGE: Record<string, string> = {
  customer: "bg-gray-100 text-gray-600",
  shop_owner: "bg-blue-50 text-blue-600",
  delivery_partner: "bg-violet-50 text-violet-600",
  admin: "bg-amber-50 text-amber-600",
};

export function UsersTab({ selfId }: { selfId: string | null }) {
  const [summary, setSummary] = useState<UsersSummary | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [s, u] = await Promise.all([apiFetch("/admin/users-summary"), apiFetch("/admin/users")]);
      setSummary(s);
      setUsers(u);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function changeRole(user: AdminUser, role: string) {
    if (role === user.role) return;
    if (role === "admin" && !window.confirm(`Grant ${user.email} full admin access?`)) return;

    setSavingId(user.id);
    try {
      await apiFetch(`/admin/users/${user.id}/role`, { method: "PATCH", body: JSON.stringify({ role }) });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingId(null);
    }
  }

  async function toggleSuspend(user: AdminUser) {
    if (!user.is_suspended && !window.confirm(`Suspend ${user.email}? They won't be able to use their account.`)) {
      return;
    }
    setSavingId(user.id);
    try {
      await apiFetch(`/admin/users/${user.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_suspended: !user.is_suspended }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingId(null);
    }
  }

  if (loading) return <div className="p-8"><p className="text-sm text-gray-400">Loading…</p></div>;
  if (error) return <div className="p-8"><p className="text-sm text-red-500">{error}</p></div>;

  const cards = summary
    ? [
        { label: "Total Customers", value: summary.total_customers },
        { label: "Shop Owners", value: summary.shop_owners },
        { label: "Delivery Partners", value: summary.delivery_partners },
      ]
    : [];

  return (
    <div className="p-8 space-y-5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-2xl border border-gray-100 p-5">
            <p className="text-sm text-gray-500">{c.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{c.value.toLocaleString("en-IN")}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
              <th className="px-5 py-3 font-medium">User</th>
              <th className="px-5 py-3 font-medium">Email</th>
              <th className="px-5 py-3 font-medium">Role</th>
              <th className="px-5 py-3 font-medium">Orders</th>
              <th className="px-5 py-3 font-medium">Joined</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isSelf = u.id === selfId;
              const initials = (u.full_name ?? u.email)
                .split(" ")
                .map((p) => p[0])
                .filter(Boolean)
                .slice(0, 2)
                .join("")
                .toUpperCase();
              return (
                <tr key={u.id} className="border-b border-gray-50 last:border-0">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-blue-500 text-white text-[11px] font-semibold flex items-center justify-center shrink-0">
                        {initials || "?"}
                      </div>
                      <span className="font-medium text-gray-900">
                        {u.full_name ?? "—"} {isSelf && <span className="text-xs text-gray-400 font-normal">(you)</span>}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-500">{u.email}</td>
                  <td className="px-5 py-3">
                    <select
                      value={u.role}
                      disabled={isSelf || savingId === u.id}
                      onChange={(e) => changeRole(u, e.target.value)}
                      title={isSelf ? "You can't change your own role here" : "Change role"}
                      className={`text-xs font-medium rounded-full px-2.5 py-1 border-0 outline-none disabled:opacity-60 ${ROLE_BADGE[u.role] ?? "bg-gray-100 text-gray-600"}`}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABELS[r]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-5 py-3 text-gray-500">{u.orders_count}</td>
                  <td className="px-5 py-3 text-gray-400">
                    {new Date(u.created_at).toLocaleDateString("en-IN", { month: "short", year: "numeric" })}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`text-xs font-medium rounded-full px-2.5 py-1 ${
                        u.is_suspended ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-600"
                      }`}
                    >
                      {u.is_suspended ? "Suspended" : "Active"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => toggleSuspend(u)}
                      disabled={isSelf || savingId === u.id}
                      className="text-xs text-red-600 hover:underline disabled:opacity-40 disabled:no-underline"
                      title={isSelf ? "You can't suspend your own account" : undefined}
                    >
                      {u.is_suspended ? "Reactivate" : "Suspend"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
