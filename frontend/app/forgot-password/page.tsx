"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { useGuestOnly } from "@/lib/useGuestOnly";

export default function ForgotPasswordPage() {
  const { checking } = useGuestOnly();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    setSent(true);
  }

  if (checking) {
    return (
      <AuthLayout title="Reset your password" subtitle="We'll email you a link to get back in">
        <p className="text-sm text-gray-400">Loading…</p>
      </AuthLayout>
    );
  }

  if (sent) {
    return (
      <AuthLayout title="Check your email" subtitle="Password reset">
        <p className="text-sm text-gray-600">
          If an account exists for <span className="font-medium">{email}</span>, we&apos;ve sent a link to reset
          your password. Open it on this device to continue.
        </p>
        <Link href="/login" className="text-sm text-blue-600 hover:underline block">
          ← Back to sign in
        </Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to get back in">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-sm text-gray-700 mb-1 block">Email address</label>
          <input
            type="email"
            required
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 transition"
        >
          {loading ? "Sending…" : "Send reset link"}
        </button>
      </form>

      <p className="text-sm text-center text-gray-600">
        <Link href="/login" className="text-blue-600 font-medium hover:underline">
          ← Back to sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
