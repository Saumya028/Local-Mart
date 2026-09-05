export const metadata = { title: "Privacy Policy — LocalMart" };

export default function PrivacyPage() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12 space-y-6 text-sm text-gray-700">
      <h1 className="text-2xl font-bold text-gray-900">Privacy Policy</h1>

      <p className="rounded-md bg-yellow-50 border border-yellow-200 px-4 py-3 text-yellow-800">
        <strong>This is a working template, not a finished legal document.</strong>{" "}
        It accurately describes what this codebase actually does with data as of
        Phase 7 — it has not been reviewed by a lawyer, and doesn&rsquo;t account for
        jurisdiction-specific requirements (GDPR, CCPA, DPDP, etc.) your actual
        launch may need. Replace this notice once it has been reviewed.
      </p>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">What we collect</h2>
        <p>
          Account details (email, name) via Supabase Auth; addresses you add to
          your account; orders, order items, and payment status (never raw card
          details — see &ldquo;Payments&rdquo; below); and, if error tracking is
          enabled, technical details about crashes (see &ldquo;Error tracking&rdquo;).
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Third parties we use</h2>
        <ul className="list-disc list-inside space-y-1">
          <li><strong>Supabase</strong> — authentication and our database.</li>
          <li><strong>Razorpay</strong> — payment processing (see &ldquo;Payments&rdquo;).</li>
          <li><strong>Upstash Redis</strong> — short-lived cart and cache data.</li>
          <li>
            <strong>Sentry</strong> (optional, off by default) — error reports, if a
            site operator has configured it. We do not send request bodies or
            cookies to Sentry by default.
          </li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Payments</h2>
        <p>
          Card details are entered directly into Razorpay&rsquo;s own hosted
          checkout widget and never touch our servers — we only ever see a
          payment status and a Razorpay-issued reference ID.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Your choices</h2>
        <p>
          You can view and edit your addresses from your Profile page. To request
          deletion of your account or data, contact us using the details below.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Contact</h2>
        <p>Questions about this policy: replace with a real support address before launch.</p>
      </section>
    </main>
  );
}
