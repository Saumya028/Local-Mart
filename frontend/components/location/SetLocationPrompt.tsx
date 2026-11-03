"use client";

import { LocationChoices } from "./LocationChoices";

/** Shown instead of shop/product lists until a delivery location is set. */
export function SetLocationPrompt({ className = "" }: { className?: string }) {
  return (
    <div className={`max-w-md mx-auto text-center space-y-4 border border-gray-100 rounded-2xl p-8 bg-white ${className}`}>
      <div className="text-4xl">📍</div>
      <h2 className="text-lg font-bold text-gray-900">Where should we deliver?</h2>
      <p className="text-sm text-gray-500">
        Every shop sets how far it delivers. Tell us where you are and we&apos;ll show only the shops that can reach you.
      </p>
      <div className="text-left">
        <LocationChoices />
      </div>
    </div>
  );
}
