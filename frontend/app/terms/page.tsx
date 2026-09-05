export const metadata = { title: "Terms of Service — LocalMart" };

export default function TermsPage() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12 space-y-6 text-sm text-gray-700">
      <h1 className="text-2xl font-bold text-gray-900">Terms of Service</h1>

      <p className="rounded-md bg-yellow-50 border border-yellow-200 px-4 py-3 text-yellow-800">
        <strong>This is a working template, not a finished legal document.</strong>{" "}
        Have it reviewed by a lawyer before this application handles real
        transactions.
      </p>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Accounts &amp; roles</h2>
        <p>
          Every account starts as a customer. Selling on LocalMart requires an
          admin to grant seller access to your account first — you can&rsquo;t make
          yourself a seller by creating a shop.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Orders &amp; payments</h2>
        <p>
          Prices and stock are re-verified by our servers at checkout, not trusted
          from what your browser last displayed. Payment is processed by
          Razorpay; we never see or store your full card details.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Sellers</h2>
        <p>
          Sellers are responsible for their own product listings, pricing, and
          stock accuracy. LocalMart may deactivate a shop that violates these
          terms or applicable law.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Changes</h2>
        <p>We may update these terms; continued use after a change means you accept the update.</p>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-900">Contact</h2>
        <p>Replace with a real support address before launch.</p>
      </section>
    </main>
  );
}
