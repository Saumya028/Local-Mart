"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import {
  CustomerType,
  panFromGstin,
  validateDob,
  validateGstin,
  validatePan,
  validatePhone,
} from "@/lib/customerFields";
import {
  AccountTypeToggle,
  BusinessFields,
  PersonalFields,
  SectionTitle,
} from "@/components/customer/FormParts";
import { AccountProfile } from "./types";

export function SettingsTab({ profile, onUpdated }: { profile: AccountProfile; onUpdated: (p: AccountProfile) => void }) {
  const [customerType, setCustomerType] = useState<CustomerType>(profile.customer_type ?? "individual");
  const [personal, setPersonal] = useState({
    full_name: profile.full_name ?? "",
    phone: profile.phone ?? "",
    date_of_birth: profile.date_of_birth ?? "",
    gender: profile.gender ?? "",
  });
  const [business, setBusiness] = useState({
    business_name: profile.business_name ?? "",
    gstin: profile.gstin ?? "",
    pan: profile.pan ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Accounts created before these fields existed (and phone-only logins)
  // have them empty — nudge once rather than silently showing blanks.
  const incomplete = !profile.date_of_birth || !profile.gender || !profile.phone;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);

    const problem =
      validatePhone(personal.phone) ??
      validateDob(personal.date_of_birth) ??
      (customerType === "business"
        ? validateGstin(business.gstin) ??
          (business.pan ? validatePan(business.pan) : null) ??
          (business.pan && business.pan.toUpperCase() !== panFromGstin(business.gstin)
            ? "PAN doesn't match the PAN inside the GSTIN"
            : null)
        : null);
    if (problem) {
      setError(problem);
      return;
    }

    setSaving(true);
    try {
      const updated: AccountProfile = await apiFetch("/auth/me", {
        method: "PATCH",
        body: JSON.stringify({
          full_name: personal.full_name.trim() || null,
          phone: personal.phone.trim() || null,
          date_of_birth: personal.date_of_birth || null,
          gender: personal.gender || null,
          customer_type: customerType,
          business_name: customerType === "business" ? business.business_name.trim() || null : null,
          gstin: customerType === "business" ? business.gstin.trim() || null : null,
          pan: customerType === "business" ? business.pan.trim() || null : null,
        }),
      });
      onUpdated(updated);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 max-w-md">
      <h2 className="font-semibold text-gray-900 mb-4">Account Settings</h2>
      {incomplete && (
        <p className="text-xs bg-amber-50 text-amber-700 rounded-lg px-3 py-2 mb-4">
          Please complete your profile — we need your mobile number, date of birth and gender.
        </p>
      )}
      <form onSubmit={handleSubmit} className="space-y-3">
        <SectionTitle>Account type</SectionTitle>
        <AccountTypeToggle value={customerType} onChange={setCustomerType} />
        {customerType === "business" && profile.customer_type === "business" && (
          <p
            className={`text-xs rounded-lg px-3 py-2 ${
              profile.gst_verified ? "bg-emerald-50 text-emerald-700" : "bg-gray-50 text-gray-500"
            }`}
          >
            {profile.gst_verified
              ? "GSTIN verified — GST benefits apply to your orders."
              : "GSTIN not verified yet — you shop as a normal customer until it is."}
          </p>
        )}

        <SectionTitle>Personal details</SectionTitle>
        <PersonalFields value={personal} onChange={(patch) => setPersonal((p) => ({ ...p, ...patch }))} />

        {customerType === "business" && (
          <>
            <SectionTitle>Business details</SectionTitle>
            <BusinessFields value={business} onChange={(patch) => setBusiness((b) => ({ ...b, ...patch }))} />
            <p className="text-xs text-gray-400">Changing your GSTIN means it needs to be verified again.</p>
          </>
        )}

        <div>
          <label className="text-sm text-gray-700 mb-1 block">Email</label>
          <input
            value={profile.email ?? "No email on file (signed in by phone)"}
            disabled
            className="w-full border border-gray-100 bg-gray-50 rounded-lg px-3 py-2.5 text-sm text-gray-400"
          />
          <p className="text-xs text-gray-400 mt-1">Managed by your login provider — not editable here.</p>
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}
        {saved && !error && <p className="text-sm text-emerald-600">Saved.</p>}

        <button
          type="submit"
          disabled={saving}
          className="bg-blue-600 text-white rounded-lg px-5 py-2 text-sm font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      </form>
    </div>
  );
}
