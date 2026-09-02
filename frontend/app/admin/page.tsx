"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";

type AdminUser = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  created_at: string;
};
type AdminShop = {
  id: string;
  name: string;
  category: string;
  rating: number;
  is_active: boolean;
  created_at: string;
  owner_id: string;
  owner_email: string;
};
type Metrics = {
  total_users: number;
  total_shop_owners: number;
  total_admins: number;
  total_shops: number;
  active_shops: number;
  total_products: number;
  active_products: number;
  total_orders: number;
  confirmed_orders: number;
  gmv: string;
};
type AuditEntry = {
  id: string;
  admin_email: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

const ROLES = ["customer", "shop_owner", "admin"] as const;

export default function AdminPanelPage() {
  const { profile, loading: authLoading, loggedIn } = useAuth();
  const [tab, setTab] = useState<"users" | "shops" | "metrics" | "audit">("metrics");

  const isAdmin = profile?.role === "admin";

  if (authLoading) {
    return (
      <main className="max-w-5xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading…</p>
      </main>
    );
  }

  if (!loggedIn) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 space-y-3">
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-sm text-gray-500">Log in to continue.</p>
      </main>
    );
  }

  // Same pattern as the Shop Dashboard: the frontend never even attempts
  // a role-gated request unless it already knows the role allows it —
  // the backend enforces this independently on every /admin/* endpoint
  // via require_role("admin"), so this check is a UX nicety, not the
  // real security boundary.
  if (!isAdmin) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 space-y-3">
        <h1 className="text-2xl font-bold">Admin Panel</h1>
        <p className="text-sm text-gray-500">
          This area is restricted to platform admins. If you believe your
          account should have access, contact an existing admin.
        </p>
      </main>
    );
  }

  return (
    <main className="max-w-5xl mx-auto px-6 py-10 space-y-6">
      <h1 className="text-2xl font-bold">Admin Panel</h1>

      <div className="flex gap-4 border-b text-sm">
        {(["metrics", "users", "shops", "audit"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 capitalize ${
              tab === t ? "border-b-2 border-blue-600 text-blue-600 font-medium" : "text-gray-500"
            }`}
          >
            {t === "audit" ? "Audit Log" : t}
          </button>
        ))}
      </div>

      {tab === "metrics" && <MetricsTab />}
      {tab === "users" && <UsersTab selfId={profile?.id ?? null} />}
      {tab === "shops" && <ShopsTab />}
      {tab === "audit" && <AuditTab />}
    </main>
  );
}

function MetricsTab() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/admin/metrics")
      .then(setMetrics)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-gray-400 pt-4">Loading metrics…</p>;
  if (error) return <p className="text-sm text-red-500 pt-4">{error}</p>;
  if (!metrics) return null;

  const cards: [string, string | number][] = [
    ["Total users", metrics.total_users],
    ["Shop owners", metrics.total_shop_owners],
    ["Admins", metrics.total_admins],
    ["Total shops", metrics.total_shops],
    ["Active shops", metrics.active_shops],
    ["Total products", metrics.total_products],
    ["Active products", metrics.active_products],
    ["Total orders", metrics.total_orders],
    ["Confirmed orders", metrics.confirmed_orders],
    ["GMV (confirmed)", `₹${metrics.gmv}`],
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-4">
      {cards.map(([label, value]) => (
        <div key={label} className="border rounded-lg p-4">
          <p className="text-xs text-gray-500">{label}</p>
          <p className="text-2xl font-bold">{value}</p>
        </div>
      ))}
    </div>
  );
}

function UsersTab({ selfId }: { selfId: string | null }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const query = search ? `?q=${encodeURIComponent(search)}` : "";
      const data: AdminUser[] = await apiFetch(`/admin/users${query}`);
      setUsers(data);
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

  async function changeRole(user: AdminUser, role: string) {
    if (role === user.role) return;

    // Promoting someone to admin is a real privilege escalation — worth
    // one extra confirmation click, not just a dropdown selection, since
    // a misclick here is far more consequential than a typo'd product name.
    if (role === "admin" && !window.confirm(`Grant ${user.email} full admin access?`)) {
      return;
    }

    setSavingId(user.id);
    try {
      await apiFetch(`/admin/users/${user.id}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="space-y-4 pt-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        className="flex gap-2"
      >
        <input
          placeholder="Search by email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border rounded-md px-3 py-2 text-sm flex-1"
        />
        <button type="submit" className="text-sm border rounded-md px-3 py-2">
          Search
        </button>
      </form>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-400">Loading users…</p>
      ) : users.length === 0 ? (
        <p className="text-sm text-gray-400">No users found.</p>
      ) : (
        <div className="space-y-3">
          {users.map((u) => {
            const isSelf = u.id === selfId;
            return (
              <div key={u.id} className="border rounded-lg p-4 flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">
                    {u.email} {isSelf && <span className="text-xs text-gray-400">(you)</span>}
                  </p>
                  <p className="text-xs text-gray-500">
                    {u.full_name ?? "No name set"} · joined{" "}
                    {new Date(u.created_at).toLocaleDateString()}
                  </p>
                </div>
                <select
                  value={u.role}
                  disabled={isSelf || savingId === u.id}
                  onChange={(e) => changeRole(u, e.target.value)}
                  title={isSelf ? "You can't change your own role here" : "Change role"}
                  className="border rounded-md px-2 py-1 text-sm capitalize disabled:opacity-50"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ShopsTab() {
  const [shops, setShops] = useState<AdminShop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data: AdminShop[] = await apiFetch("/admin/shops");
      setShops(data);
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

  async function toggleActive(shop: AdminShop) {
    setSavingId(shop.id);
    try {
      await apiFetch(`/admin/shops/${shop.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !shop.is_active }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingId(null);
    }
  }

  if (loading) return <p className="text-sm text-gray-400 pt-4">Loading shops…</p>;
  if (error) return <p className="text-sm text-red-500 pt-4">{error}</p>;
  if (shops.length === 0) return <p className="text-sm text-gray-400 pt-4">No shops yet.</p>;

  return (
    <div className="space-y-3 pt-4">
      {shops.map((s) => (
        <div key={s.id} className="border rounded-lg p-4 flex items-center justify-between">
          <div>
            <p className="font-medium text-sm">
              {s.name} {!s.is_active && <span className="text-xs text-gray-400">(deactivated)</span>}
            </p>
            <p className="text-xs text-gray-500">
              {s.category} · owned by {s.owner_email} · rating {s.rating.toFixed(1)}
            </p>
          </div>
          <button
            onClick={() => toggleActive(s)}
            disabled={savingId === s.id}
            className="text-xs text-blue-600 underline disabled:opacity-50"
          >
            {s.is_active ? "Deactivate" : "Reactivate"}
          </button>
        </div>
      ))}
    </div>
  );
}

function AuditTab() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/admin/audit-log")
      .then(setEntries)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-gray-400 pt-4">Loading audit log…</p>;
  if (error) return <p className="text-sm text-red-500 pt-4">{error}</p>;
  if (entries.length === 0) return <p className="text-sm text-gray-400 pt-4">No admin actions yet.</p>;

  return (
    <div className="space-y-3 pt-4">
      {entries.map((e) => (
        <div key={e.id} className="border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium capitalize">{e.action.replace(/_/g, " ")}</p>
            <p className="text-xs text-gray-400">{new Date(e.created_at).toLocaleString()}</p>
          </div>
          <p className="text-xs text-gray-500">
            by {e.admin_email ?? "unknown admin"} · target: {e.target_type}
            {e.target_id ? ` (${e.target_id.slice(0, 8)})` : ""}
          </p>
          {Object.keys(e.details).length > 0 && (
            <pre className="text-xs text-gray-500 bg-gray-50 rounded p-2 mt-2 overflow-x-auto">
              {JSON.stringify(e.details, null, 2)}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
