"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { StaffMember, staffRoleLabel, timeAgo } from "./types";

type NewStaffForm = { full_name: string; email: string; password: string; staff_role: "manager" | "delivery_partner" };

const EMPTY_FORM: NewStaffForm = { full_name: "", email: "", password: "", staff_role: "delivery_partner" };

export function StaffTab({ shopId }: { shopId: string }) {
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<NewStaffForm>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  // Shown once, right after a successful create — this IS the "owner
  // sets a password, shown once on screen to share manually" flow: we
  // never re-fetch or re-display a password after this point, since
  // Supabase only ever stores it hashed from here on.
  const [justCreated, setJustCreated] = useState<{ email: string; password: string } | null>(null);

  const [resettingId, setResettingId] = useState<string | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data: StaffMember[] = await apiFetch(`/dashboard/staff?shop_id=${shopId}`);
      setStaff(data);
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
  }, [shopId]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setCreating(true);
    try {
      await apiFetch("/dashboard/staff", {
        method: "POST",
        body: JSON.stringify({ ...form, shop_id: shopId }),
      });
      setJustCreated({ email: form.email, password: form.password });
      setForm(EMPTY_FORM);
      setShowForm(false);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCreating(false);
    }
  }

  async function toggleSuspend(member: StaffMember) {
    setBusyId(member.id);
    try {
      await apiFetch(`/dashboard/staff/${member.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_suspended: !member.is_suspended }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  async function submitReset(memberId: string) {
    if (resetPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    setBusyId(memberId);
    try {
      await apiFetch(`/dashboard/staff/${memberId}`, {
        method: "PATCH",
        body: JSON.stringify({ new_password: resetPassword }),
      });
      setResettingId(null);
      setResetPassword("");
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  async function remove(member: StaffMember) {
    if (!confirm(`Remove ${member.full_name || member.email}? They'll lose access immediately.`)) return;
    setBusyId(member.id);
    try {
      await apiFetch(`/dashboard/staff/${member.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="p-8 space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Staff</h2>
          <p className="text-sm text-gray-500">
            Create logins for your managers and delivery team — each sees only what their role needs.
          </p>
        </div>
        <button
          onClick={() => {
            setShowForm((v) => !v);
            setJustCreated(null);
          }}
          className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2"
        >
          {showForm ? "Cancel" : "+ Add Staff"}
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {justCreated && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-2">
          <p className="text-sm font-medium text-emerald-800">
            Account created — share these with them now. This password won&apos;t be shown again.
          </p>
          <div className="bg-white border border-emerald-100 rounded-lg px-3 py-2 text-sm font-mono flex flex-col gap-1">
            <span>Email: {justCreated.email}</span>
            <span>Password: {justCreated.password}</span>
          </div>
          <button
            onClick={() => {
              navigator.clipboard?.writeText(
                `Email: ${justCreated.email}\nPassword: ${justCreated.password}`
              );
            }}
            className="text-xs font-medium text-emerald-700 underline"
          >
            Copy to clipboard
          </button>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white border border-gray-100 rounded-2xl p-5 space-y-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500">Full name</label>
              <input
                required
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">Email</label>
              <input
                required
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">Temporary password</label>
              <input
                required
                minLength={8}
                type="text"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="At least 8 characters"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500">Role</label>
              <select
                value={form.staff_role}
                onChange={(e) => setForm({ ...form, staff_role: e.target.value as "manager" | "delivery_partner" })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1 bg-white"
              >
                <option value="delivery_partner">Delivery — orders only</option>
                <option value="manager">Manager — returns, inventory, products, dashboard & analytics</option>
              </select>
            </div>
          </div>
          <button
            type="submit"
            disabled={creating}
            className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create account"}
          </button>
        </form>
      )}

      <div className="bg-white border border-gray-100 rounded-2xl overflow-hidden">
        {loading ? (
          <p className="text-sm text-gray-400 p-6">Loading staff…</p>
        ) : staff.length === 0 ? (
          <p className="text-sm text-gray-400 p-6">
            No staff yet — add a manager or delivery account above to share the workload.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50/50">
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Email</th>
                <th className="px-5 py-3 font-medium">Role</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Added</th>
                <th className="px-5 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((m) => (
                <tr key={m.id} className="border-b border-gray-50 last:border-0 align-top">
                  <td className="px-5 py-3 text-gray-800">{m.full_name || "—"}</td>
                  <td className="px-5 py-3 text-gray-500">{m.email}</td>
                  <td className="px-5 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                      {staffRoleLabel(m.role)}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        m.is_suspended ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {m.is_suspended ? "Suspended" : "Active"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-400">{timeAgo(m.created_at)}</td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => toggleSuspend(m)}
                        disabled={busyId === m.id}
                        className="text-xs font-medium text-gray-600 border border-gray-200 rounded-md px-2.5 py-1 disabled:opacity-50"
                      >
                        {m.is_suspended ? "Reactivate" : "Suspend"}
                      </button>
                      <button
                        onClick={() => {
                          setResettingId(resettingId === m.id ? null : m.id);
                          setResetPassword("");
                        }}
                        className="text-xs font-medium text-gray-600 border border-gray-200 rounded-md px-2.5 py-1"
                      >
                        Reset password
                      </button>
                      <button
                        onClick={() => remove(m)}
                        disabled={busyId === m.id}
                        className="text-xs font-medium text-red-600 border border-red-200 rounded-md px-2.5 py-1 disabled:opacity-50"
                      >
                        Remove
                      </button>
                    </div>
                    {resettingId === m.id && (
                      <div className="flex items-center gap-2 mt-2">
                        <input
                          type="text"
                          value={resetPassword}
                          onChange={(e) => setResetPassword(e.target.value)}
                          placeholder="New password (8+ chars)"
                          className="border border-gray-200 rounded-md px-2 py-1 text-xs"
                        />
                        <button
                          onClick={() => submitReset(m.id)}
                          disabled={busyId === m.id}
                          className="text-xs font-medium bg-gray-900 text-white rounded-md px-2.5 py-1 disabled:opacity-50"
                        >
                          Save
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
