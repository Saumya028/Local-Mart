"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { AuthLayout } from "@/components/auth/AuthLayout";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    // Clicking the link from forgot-password's email redirects here with
    // a recovery token in the URL — supabase-js reads it automatically
    // and fires PASSWORD_RECOVERY once the session is established. We
    // also check for an already-live session on mount in case that
    // exchange finished before this listener was attached.
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) setReady(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") setReady(true);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    setDone(true);
  }

  if (done) {
    return (
      <AuthLayout title="Password updated" subtitle="You're all set">
        <p className="text-sm text-gray-600">Your password has been changed.</p>
        <button
          onClick={() => router.push("/")}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium transition"
        >
          Continue to LocalMart
        </button>
      </AuthLayout>
    );
  }

  if (!ready) {
    return (
      <AuthLayout title="Reset your password" subtitle="Verifying your link">
        <p className="text-sm text-gray-500">
          If this doesn&apos;t update in a moment, the link may have expired —{" "}
          <Link href="/forgot-password" className="text-blue-600 hover:underline">
            request a new one
          </Link>
          .
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Set a new password" subtitle="Choose something you haven't used before">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-sm text-gray-700 mb-1 block">New password</label>
          <input
            type="password"
            required
            minLength={6}
            placeholder="At least 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="text-sm text-gray-700 mb-1 block">Confirm new password</label>
          <input
            type="password"
            required
            placeholder="Re-enter your new password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 transition"
        >
          {loading ? "Saving…" : "Save new password"}
        </button>
      </form>
    </AuthLayout>
  );
}
