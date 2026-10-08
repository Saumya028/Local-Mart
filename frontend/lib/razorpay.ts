// Razorpay's hosted checkout popup, loaded on demand so it never touches
// pages that don't sell anything. Shared by every "pay LocalMart" flow
// (sponsorship plans, banners).
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void; on: (e: string, cb: () => void) => void };
  }
}

export function loadRazorpay(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}
