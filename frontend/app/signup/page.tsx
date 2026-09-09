"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { AuthLayout } from "@/components/auth/AuthLayout";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
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

    setLoading(true);
    // `full_name` here lands in the JWT's `user_metadata` claim — the
    // backend reads it back out on first login to fill in the profile
    // row (see backend/app/core/security.py's get_current_user), so it
    // doesn't need its own separate "set your name" step afterward.
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName } },
    });
    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    if (data.session) {
      // Email confirmation is off for this project — signUp already
      // returned a live session, so there's nothing to wait on.
      router.push("/");
      router.refresh();
      return;
    }

    // Email confirmation is required — no session yet, so there's
    // nothing to redirect into until they click the link.
    setCheckEmail(true);
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
        <div>
          <label className="text-sm text-gray-700 mb-1 block">Full name</label>
          <input
            required
            placeholder="Your name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
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
        <div>
          <label className="text-sm text-gray-700 mb-1 block">Confirm password</label>
          <input
            type={showPassword ? "text" : "password"}
            required
            placeholder="Re-enter your password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <p className="text-xs text-gray-400">
          Every account starts as a customer. Selling on LocalMart requires your account to be approved by a
          platform admin afterward.
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
