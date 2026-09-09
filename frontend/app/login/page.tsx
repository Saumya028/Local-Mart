"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { setPostLoginRedirect, consumePostLoginRedirect } from "@/lib/postLoginRedirect";

type Tab = "email" | "phone";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("email");
  const [shortcut, setShortcut] = useState<"shop_owner" | "admin" | null>(null);

  // Email + password
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Phone OTP
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function afterLogin() {
    router.push(consumePostLoginRedirect("/"));
    router.refresh();
  }

  async function handleEmailSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    afterLogin();
  }

  async function handleSendCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    // Requires a phone/SMS provider (e.g. Twilio) configured in your
    // Supabase project's Auth settings — see frontend/README.md's
    // "Phone sign-in setup" section. Without that, Supabase accepts the
    // request but no SMS is ever actually sent.
    const { error } = await supabase.auth.signInWithOtp({ phone });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    setOtpSent(true);
  }

  async function handleVerifyCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.verifyOtp({ phone, token: otp, type: "sms" });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    afterLogin();
  }

  function toggleShortcut(target: "shop_owner" | "admin") {
    if (shortcut === target) {
      setShortcut(null);
      setPostLoginRedirect("/");
      return;
    }
    setShortcut(target);
    setPostLoginRedirect(target === "shop_owner" ? "/shop/dashboard" : "/admin");
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your LocalMart account">
      <div className="flex bg-gray-100 rounded-xl p-1">
        <button
          type="button"
          onClick={() => setTab("email")}
          className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium rounded-lg py-2 transition-colors ${
            tab === "email" ? "bg-white shadow-sm text-gray-900" : "text-gray-500"
          }`}
        >
          ✉ Email
        </button>
        <button
          type="button"
          onClick={() => setTab("phone")}
          className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium rounded-lg py-2 transition-colors ${
            tab === "phone" ? "bg-white shadow-sm text-gray-900" : "text-gray-500"
          }`}
        >
          📞 Phone
        </button>
      </div>

      {tab === "email" ? (
        <form onSubmit={handleEmailSubmit} className="space-y-3">
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
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-gray-700">Password</label>
              <Link href="/forgot-password" className="text-xs text-blue-600 hover:underline">
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                placeholder="Enter your password"
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

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 transition"
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      ) : (
        <form onSubmit={otpSent ? handleVerifyCode : handleSendCode} className="space-y-3">
          <div>
            <label className="text-sm text-gray-700 mb-1 block">Phone number</label>
            <input
              type="tel"
              required
              disabled={otpSent}
              placeholder="+91 98765 43210"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>

          {otpSent && (
            <div>
              <label className="text-sm text-gray-700 mb-1 block">Verification code</label>
              <input
                required
                inputMode="numeric"
                placeholder="6-digit code"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={() => {
                  setOtpSent(false);
                  setOtp("");
                }}
                className="text-xs text-blue-600 hover:underline mt-1"
              >
                Use a different number
              </button>
            </div>
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 transition"
          >
            {loading ? "Please wait…" : otpSent ? "Verify & Sign In" : "Send Code"}
          </button>
        </form>
      )}

      <p className="text-sm text-center text-gray-600">
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="text-blue-600 font-medium hover:underline">
          Sign up free
        </Link>
      </p>

      <p className="text-xs text-center text-gray-400">
        By signing in, you agree to our{" "}
        <Link href="/terms" className="underline hover:text-gray-600">
          Terms
        </Link>{" "}
        and{" "}
        <Link href="/privacy" className="underline hover:text-gray-600">
          Privacy Policy
        </Link>
      </p>

      <div className="pt-2 border-t border-gray-100 space-y-2">
        <p className="text-xs text-center text-gray-400">Or sign in as</p>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => toggleShortcut("shop_owner")}
            className={`text-sm font-medium rounded-lg py-2 border transition-colors ${
              shortcut === "shop_owner" ? "border-blue-500 text-blue-700 bg-blue-50" : "border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            Shop Owner
          </button>
          <button
            type="button"
            onClick={() => toggleShortcut("admin")}
            className={`text-sm font-medium rounded-lg py-2 border transition-colors ${
              shortcut === "admin" ? "border-blue-500 text-blue-700 bg-blue-50" : "border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            Admin
          </button>
        </div>
        {shortcut && (
          <p className="text-xs text-center text-gray-400">
            Signing in will take you straight to the {shortcut === "shop_owner" ? "Shop Dashboard" : "Admin Panel"} —
            your account still needs that role to actually use it.
          </p>
        )}
      </div>
    </AuthLayout>
  );
}
