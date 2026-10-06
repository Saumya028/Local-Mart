"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { useGuestOnly } from "@/lib/useGuestOnly";
import { consumePostLoginRedirect } from "@/lib/postLoginRedirect";
import {
  AddressValues,
  CustomerType,
  EMPTY_ADDRESS,
  panFromGstin,
  validateAddress,
  validateDob,
  validateGstin,
  validatePan,
  validatePhone,
} from "@/lib/customerFields";
import {
  AccountTypeToggle,
  AddressFields,
  BusinessFields,
  Field,
  PersonalFields,
  SectionTitle,
  inputCls,
} from "@/components/customer/FormParts";

export default function SignupPage() {
  const router = useRouter();
  const { checking } = useGuestOnly();
  const [customerType, setCustomerType] = useState<CustomerType>("individual");
  const [personal, setPersonal] = useState({ full_name: "", phone: "", date_of_birth: "", gender: "" });
  const [business, setBusiness] = useState({ business_name: "", gstin: "", pan: "" });
  const [address, setAddress] = useState<AddressValues>(EMPTY_ADDRESS);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [checkEmail, setCheckEmail] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    // Instant feedback only — the backend re-validates everything when it
    // creates the profile, so this can never be the only line of defence.
    const problem =
      validatePhone(personal.phone) ??
      validateDob(personal.date_of_birth) ??
      (customerType === "business"
        ? validateGstin(business.gstin) ??
          (business.pan ? validatePan(business.pan) : null) ??
          (business.pan && business.pan !== panFromGstin(business.gstin)
            ? "PAN doesn't match the PAN inside the GSTIN"
            : null)
        : null) ??
      validateAddress(address, false);
    if (problem) {
      setError(problem);
      return;
    }

    setLoading(true);
    // Everything under `data` lands in the JWT's `user_metadata` claim —
    // the backend reads it back out on first login to fill in the profile
    // row and the first saved address (see backend/app/core/security.py's
    // get_current_user), so none of it needs a separate step afterward.
    // This works the same whether or not email confirmation is on.
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: personal.full_name.trim(),
          phone: personal.phone.trim(),
          date_of_birth: personal.date_of_birth,
          gender: personal.gender,
          customer_type: customerType,
          ...(customerType === "business"
            ? {
                business_name: business.business_name.trim(),
                gstin: business.gstin.trim(),
                pan: business.pan.trim() || undefined,
              }
            : {}),
          address: {
            label: address.label,
            line1: address.line1.trim(),
            line2: address.line2.trim() || undefined,
            landmark: address.landmark.trim() || undefined,
            city: address.city.trim(),
            state: address.state,
            pincode: address.pincode.trim(),
          },
        },
      },
    });
    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    if (data.session) {
      // Email confirmation is off for this project — signUp already
      // returned a live session, so there's nothing to wait on. Same
      // redirect mechanism the Login page uses: if they got here via
      // "List Your Shop" (see /shop/dashboard), this sends them straight
      // back there instead of to the homepage.
      router.push(consumePostLoginRedirect("/"));
      router.refresh();
      return;
    }

    // Email confirmation is required — no session yet, so there's
    // nothing to redirect into until they click the link.
    setCheckEmail(true);
  }

  if (checking) {
    return (
      <AuthLayout title="Create your account" subtitle="Join LocalMart in seconds">
        <p className="text-sm text-gray-400">Loading…</p>
      </AuthLayout>
    );
  }

  if (checkEmail) {
    return (
      <AuthLayout title="Check your email" subtitle="Almost there">
        <p className="text-sm text-gray-600">
          We sent a confirmation link to <span className="font-medium">{email}</span>. Click it to activate your
          account, then come back and{" "}
          <Link href="/login" className="text-blue-600 hover:underline">
            sign in
          </Link>
          .
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Create your account" subtitle="Join LocalMart in seconds">
      <form onSubmit={handleSubmit} className="space-y-3">
        <SectionTitle>Account type</SectionTitle>
        <AccountTypeToggle value={customerType} onChange={setCustomerType} />

        <SectionTitle>Personal details</SectionTitle>
        <PersonalFields value={personal} onChange={(patch) => setPersonal((p) => ({ ...p, ...patch }))} />

        {customerType === "business" && (
          <>
            <SectionTitle>Business details</SectionTitle>
            <BusinessFields value={business} onChange={(patch) => setBusiness((b) => ({ ...b, ...patch }))} />
          </>
        )}

        <SectionTitle>Delivery address</SectionTitle>
        <AddressFields
          value={address}
          onChange={(patch) => setAddress((a) => ({ ...a, ...patch }))}
          showRecipient={false}
        />

        <SectionTitle>Login details</SectionTitle>
        <Field label="Email address">
          <input
            type="email"
            required
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls}
          />
        </Field>
        <div>
          <label className="text-sm text-gray-700 mb-1 block">Password</label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              required
              minLength={6}
              placeholder="At least 6 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 pr-9"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs"
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </div>
        <Field label="Confirm password">
          <input
            type={showPassword ? "text" : "password"}
            required
            placeholder="Re-enter your password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className={inputCls}
          />
        </Field>

        <p className="text-xs text-gray-400">
          {customerType === "business"
            ? "Business accounts shop as a normal customer until your GSTIN is verified; GST benefits apply after that. "
            : ""}
          You can apply to list your own shop any time — approval of that shop listing is what a platform admin
          reviews.
        </p>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 transition"
        >
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="text-sm text-center text-gray-600">
        Already have an account?{" "}
        <Link href="/login" className="text-blue-600 font-medium hover:underline">
          Sign in
        </Link>
      </p>

      <p className="text-xs text-center text-gray-400">
        By signing up, you agree to our{" "}
        <Link href="/terms" className="underline hover:text-gray-600">
          Terms
        </Link>{" "}
        and{" "}
        <Link href="/privacy" className="underline hover:text-gray-600">
          Privacy Policy
        </Link>
      </p>
    </AuthLayout>
  );
}
