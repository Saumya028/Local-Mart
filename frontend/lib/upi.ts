// Direct UPI payments — customer pays the shop, never the platform.
// Mirrors backend/app/core/upi.py so bad input is caught before a round trip.

// <handle>@<psp>, e.g. "shopname@okaxis" or "9876543210@ybl"
const UPI_ID_RE = /^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$/;
// UTR / transaction id: 8-30 letters or digits
const PAYER_REF_RE = /^[A-Za-z0-9]{8,30}$/;

export function isValidUpiId(value: string): boolean {
  return UPI_ID_RE.test(value.trim());
}

export function isValidPayerReference(value: string): boolean {
  return PAYER_REF_RE.test(value.trim());
}

// upi://pay deep link — opens GPay / PhonePe / Paytm / BHIM on a phone
// with payee, amount and a note pre-filled.
export function buildUpiLink(upiId: string, payeeName: string, amount: string | number, note: string): string {
  const am = Number(amount).toFixed(2);
  return (
    `upi://pay?pa=${encodeURIComponent(upiId).replace("%40", "@")}` +
    `&pn=${encodeURIComponent(payeeName)}&am=${am}&cu=INR&tn=${encodeURIComponent(note)}`
  );
}

export type PaymentMethod = "upi" | "cash";
