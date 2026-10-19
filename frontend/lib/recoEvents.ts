import { apiFetch } from "./apiClient";
import type { RecoSurface, RecoVariant } from "@/components/recommendations/types";

// Shelf telemetry (impressions / clicks), batched so a page with a few
// shelves makes one request, not dozens. Fire-and-forget: measurement must
// never slow down or break the page. The server records nothing for visitors
// who opted out of personalization.
type Ev = {
  surface: RecoSurface;
  event: "impression" | "click" | "add_to_cart";
  product_id: string;
  position: number;
  run_id: string | null;
  variant: RecoVariant;
};

let queue: Ev[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;

function flush() {
  timer = null;
  const batch = queue.splice(0, 50);
  if (queue.length) timer = setTimeout(flush, 500);
  if (!batch.length) return;
  apiFetch("/recommendations/events", {
    method: "POST",
    body: JSON.stringify({ events: batch }),
    keepalive: true,
  }).catch(() => {});
}

export function trackReco(ev: Ev) {
  queue.push(ev);
  if (!timer) timer = setTimeout(flush, 1500);
}

if (typeof window !== "undefined") {
  // don't lose clicks when the person navigates away right after
  window.addEventListener("pagehide", () => {
    if (timer) clearTimeout(timer);
    flush();
  });
}
