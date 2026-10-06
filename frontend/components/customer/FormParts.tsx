"use client";

import { ReactNode } from "react";
import {
  AddressValues,
  CustomerType,
  GENDER_OPTIONS,
  INDIAN_STATES,
} from "@/lib/customerFields";

export const inputCls =
  "w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="text-sm text-gray-700 mb-1 block">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 pt-2">{children}</h3>;
}

/** Normal customer vs. Business (GST) account. */
export function AccountTypeToggle({
  value,
  onChange,
}: {
  value: CustomerType;
  onChange: (v: CustomerType) => void;
}) {
  const options: { value: CustomerType; title: string; sub: string }[] = [
    { value: "individual", title: "Individual", sub: "Shopping for yourself" },
    { value: "business", title: "Business", sub: "Buying with a GSTIN" },
  ];
  return (
    <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Account type">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`text-left border rounded-lg px-3 py-2.5 transition ${
            value === o.value ? "border-blue-600 bg-blue-50 ring-1 ring-blue-600" : "border-gray-200 hover:border-gray-300"
          }`}
        >
          <span className="block text-sm font-medium text-gray-900">{o.title}</span>
          <span className="block text-xs text-gray-500">{o.sub}</span>
        </button>
      ))}
    </div>
  );
}

export type PersonalValues = {
  full_name: string;
  phone: string;
  date_of_birth: string;
  gender: string;
};

export function PersonalFields({
  value,
  onChange,
}: {
  value: PersonalValues;
  onChange: (patch: Partial<PersonalValues>) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <>
      <Field label="Full name">
        <input
          required
          placeholder="As on your ID"
          value={value.full_name}
          onChange={(e) => onChange({ full_name: e.target.value })}
          className={inputCls}
        />
      </Field>
      <Field label="Mobile number" hint="Used by delivery partners to reach you.">
        <input
          required
          type="tel"
          inputMode="tel"
          placeholder="98765 43210"
          value={value.phone}
          onChange={(e) => onChange({ phone: e.target.value })}
          className={inputCls}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Date of birth">
          <input
            required
            type="date"
            max={today}
            value={value.date_of_birth}
            onChange={(e) => onChange({ date_of_birth: e.target.value })}
            className={inputCls}
          />
        </Field>
        <Field label="Gender">
          <select
            required
            value={value.gender}
            onChange={(e) => onChange({ gender: e.target.value })}
            className={inputCls}
          >
            <option value="">Select…</option>
            {GENDER_OPTIONS.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
    </>
  );
}

export type BusinessValues = { business_name: string; gstin: string; pan: string };

export function BusinessFields({
  value,
  onChange,
}: {
  value: BusinessValues;
  onChange: (patch: Partial<BusinessValues>) => void;
}) {
  return (
    <>
      <Field label="Registered business name">
        <input
          required
          placeholder="As on your GST certificate"
          value={value.business_name}
          onChange={(e) => onChange({ business_name: e.target.value })}
          className={inputCls}
        />
      </Field>
      <Field
        label="GSTIN"
        hint="15 characters. Your business gets GST benefits once we've verified it — until then you shop as a normal customer."
      >
        <input
          required
          maxLength={15}
          placeholder="27AAPFU0939F1ZV"
          value={value.gstin}
          onChange={(e) => onChange({ gstin: e.target.value.toUpperCase() })}
          className={`${inputCls} font-mono tracking-wide`}
        />
      </Field>
      <Field label="Business PAN (optional)">
        <input
          maxLength={10}
          placeholder="AAPFU0939F"
          value={value.pan}
          onChange={(e) => onChange({ pan: e.target.value.toUpperCase() })}
          className={`${inputCls} font-mono tracking-wide`}
        />
      </Field>
    </>
  );
}

export function AddressFields({
  value,
  onChange,
  showLabel = true,
  showRecipient = true,
  required = true,
}: {
  value: AddressValues;
  onChange: (patch: Partial<AddressValues>) => void;
  showLabel?: boolean;
  showRecipient?: boolean;
  // Turn off the browser's own `required` checks when these fields sit
  // inside ANOTHER form (checkout) — otherwise an empty, open address
  // form would block that outer form from submitting.
  required?: boolean;
}) {
  return (
    <>
      {showRecipient && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Recipient name">
            <input
              required={required}
              value={value.recipient_name}
              onChange={(e) => onChange({ recipient_name: e.target.value })}
              className={inputCls}
            />
          </Field>
          <Field label="Mobile number">
            <input
              required={required}
              type="tel"
              inputMode="tel"
              value={value.phone}
              onChange={(e) => onChange({ phone: e.target.value })}
              className={inputCls}
            />
          </Field>
        </div>
      )}
      <Field label="Flat / house no., building, street">
        <input
          required={required}
          value={value.line1}
          onChange={(e) => onChange({ line1: e.target.value })}
          className={inputCls}
        />
      </Field>
      <Field label="Area, colony, locality (optional)">
        <input value={value.line2} onChange={(e) => onChange({ line2: e.target.value })} className={inputCls} />
      </Field>
      <Field label="Landmark (optional)">
        <input
          placeholder="E.g. near the temple"
          value={value.landmark}
          onChange={(e) => onChange({ landmark: e.target.value })}
          className={inputCls}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="PIN code">
          <input
            required={required}
            inputMode="numeric"
            maxLength={6}
            placeholder="6 digits"
            value={value.pincode}
            onChange={(e) => onChange({ pincode: e.target.value.replace(/\D/g, "") })}
            className={inputCls}
          />
        </Field>
        <Field label="City / town">
          <input required={required} value={value.city} onChange={(e) => onChange({ city: e.target.value })} className={inputCls} />
        </Field>
      </div>
      <div className={showLabel ? "grid grid-cols-2 gap-3" : ""}>
        <Field label="State">
          <select required={required} value={value.state} onChange={(e) => onChange({ state: e.target.value })} className={inputCls}>
            <option value="">Select…</option>
            {INDIAN_STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        {showLabel && (
          <Field label="Save as">
            <select required={required} value={value.label} onChange={(e) => onChange({ label: e.target.value })} className={inputCls}>
              {["Home", "Work", "Other"].map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
    </>
  );
}
