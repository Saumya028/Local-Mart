"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { Shop, ShopDocument } from "./types";
import { DocumentUploader } from "./DocumentUploader";

const STATUS_COPY: Record<string, { title: string; desc: string; tone: "amber" | "red" }> = {
  pending: {
    title: "Application under review",
    desc: "An admin is reviewing this application. Once it's approved you'll be able to manage products and orders here.",
    tone: "amber",
  },
  rejected: {
    title: "Application rejected",
    desc: "This application wasn't approved. Update the documents below to send it back into the review queue.",
    tone: "red",
  },
};

const DOCS_BADGE: Record<string, { label: string; className: string }> = {
  verified: { label: "Verified", className: "bg-emerald-50 text-emerald-600" },
  submitted: { label: "Submitted — awaiting review", className: "bg-blue-50 text-blue-600" },
  pending: { label: "Action needed", className: "bg-amber-50 text-amber-600" },
};

export function ShopStatusScreen({
  shop,
  userId,
  onUpdated,
}: {
  shop: Shop;
  userId: string;
  onUpdated: () => void;
}) {
  const [documents, setDocuments] = useState<ShopDocument[]>(shop.documents);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function resubmit() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await apiFetch(`/dashboard/shops/${shop.id}`, {
        method: "PUT",
        body: JSON.stringify({ documents }),
      });
      setSaved(true);
      onUpdated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const status = STATUS_COPY[shop.approval_status] ?? STATUS_COPY.pending;
  const docsBadge = DOCS_BADGE[shop.docs_status] ?? DOCS_BADGE.pending;

  return (
    <main className="max-w-2xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{shop.name}</h1>
        <p className="text-sm text-gray-500">{shop.category}</p>
      </div>

      <div className={`rounded-2xl border p-5 ${status.tone === "red" ? "bg-red-50 border-red-100" : "bg-amber-50 border-amber-100"}`}>
        <p className={`text-sm font-semibold ${status.tone === "red" ? "text-red-700" : "text-amber-700"}`}>{status.title}</p>
        <p className="text-sm text-gray-600 mt-1">{status.desc}</p>
        {shop.rejection_reason && (
          <p className="text-sm text-gray-700 mt-3 bg-white/70 rounded-lg px-3 py-2 border border-white">
            <span className="font-medium">Note from admin: </span>
            {shop.rejection_reason}
          </p>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Verification Documents</h2>
          <span className={`text-xs font-medium rounded-full px-2.5 py-1 ${docsBadge.className}`}>{docsBadge.label}</span>
        </div>

        <DocumentUploader userId={userId} documents={documents} onChange={setDocuments} />

        {error && <p className="text-sm text-red-500">{error}</p>}
        {saved && !error && <p className="text-sm text-emerald-600">Saved — back in the admin&apos;s review queue.</p>}

        <button
          onClick={resubmit}
          disabled={saving || documents.length === 0}
          className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save documents"}
        </button>
      </div>
    </main>
  );
}
