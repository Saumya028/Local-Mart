"use client";

import { useState } from "react";

export function ProductGallery({ images, alt }: { images: string[]; alt: string }) {
  const [active, setActive] = useState(0);

  if (images.length === 0) {
    return <div className="aspect-square bg-gray-50 rounded-xl border border-gray-100" />;
  }

  return (
    <div className="space-y-3">
      {/* eslint-disable-next-line @next/next/no-img-element -- user-uploaded Supabase Storage URL, not a static asset */}
      <img
        src={images[active]}
        alt={alt}
        className="w-full aspect-square object-contain bg-white rounded-xl border border-gray-100"
      />
      {images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto">
          {images.map((url, i) => (
            <button
              key={url}
              onClick={() => setActive(i)}
              className={`w-14 h-14 shrink-0 rounded-lg border overflow-hidden ${
                i === active ? "border-blue-500 ring-1 ring-blue-500" : "border-gray-200"
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={url} alt="" className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
