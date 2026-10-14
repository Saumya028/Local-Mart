"use client";

import { useState } from "react";

const LABELS = ["", "Poor", "Fair", "Good", "Very good", "Excellent"];

/** Clickable 1–5 star picker, usable by keyboard (radio group semantics). */
export function StarInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <div>
      <div role="radiogroup" aria-label="Rating" className="flex items-center gap-1" onMouseLeave={() => setHover(0)}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            aria-label={`${n} star${n === 1 ? "" : "s"}`}
            onMouseEnter={() => setHover(n)}
            onClick={() => onChange(n)}
            className={`text-3xl leading-none transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded ${
              n <= shown ? "text-amber-400" : "text-gray-200"
            }`}
          >
            ★
          </button>
        ))}
      </div>
      <p className="text-xs text-gray-500 mt-1 h-4">{LABELS[shown]}</p>
    </div>
  );
}
