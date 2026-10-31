"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { ReportModal } from "./ReportModal";

/** "Report this shop" on a shop page. Goes straight to LocalMart support. */
export function ReportShopButton({ shopId, shopName }: { shopId: string; shopName: string }) {
  const { loggedIn } = useAuth();
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);

  if (!loggedIn) {
    return (
      <Link href="/login" className="text-xs text-gray-400 hover:text-gray-700 underline">
        Log in to report this shop
      </Link>
    );
  }
  if (sent) {
    return (
      <p className="text-xs text-gray-500">
        Thanks — LocalMart support will review your report.{" "}
        <Link href="/profile?tab=support" className="underline">
          Track it
        </Link>
      </p>
    );
  }
  return (
    <>
      <button onClick={() => setOpen(true)} className="text-xs text-gray-400 hover:text-gray-700 underline">
        Report this shop
      </button>
      {open && (
        <ReportModal
          mode="shop"
          shopId={shopId}
          shopName={shopName}
          onClose={() => setOpen(false)}
          onSubmitted={() => {
            setOpen(false);
            setSent(true);
          }}
        />
      )}
    </>
  );
}
