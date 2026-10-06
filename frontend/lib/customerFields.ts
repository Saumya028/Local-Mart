// Shared option lists + client-side validation for the customer details
// collected at signup / My Account / address forms. These mirror the
// backend's app/core/customer_validation.py — the backend is the one that
// actually enforces them; this just gives instant feedback instead of a
// round trip, so keep the two in sync.

export const INDIAN_STATES = [
  "Andaman and Nicobar Islands",
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chandigarh",
  "Chhattisgarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jammu and Kashmir",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Ladakh",
  "Lakshadweep",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Puducherry",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
];

export const GENDER_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];

export type CustomerType = "individual" | "business";

export function genderLabel(value: string | null | undefined): string {
  return GENDER_OPTIONS.find((g) => g.value === value)?.label ?? "";
}

// ---- validators: each returns an error message, or null when fine ------

export function validatePhone(v: string): string | null {
  const digits = v.replace(/[\s\-()]/g, "").replace(/^\+/, "");
  const national = digits.length === 12 && digits.startsWith("91") ? digits.slice(2) : digits.length === 11 && digits.startsWith("0") ? digits.slice(1) : digits;
  return /^[6-9][0-9]{9}$/.test(national) ? null : "Enter a valid 10-digit mobile number";
}

export function validatePincode(v: string): string | null {
  return /^[1-9][0-9]{5}$/.test(v.trim()) ? null : "PIN code must be 6 digits";
}

export function validateDob(v: string): string | null {
  if (!v) return "Date of birth is required";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "Enter a valid date of birth";
  const now = new Date();
  if (d > now) return "Date of birth can't be in the future";
  if (d.getFullYear() < now.getFullYear() - 120) return "Enter a valid date of birth";
  return null;
}

const GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function gstinCheckChar(first14: string): string {
  let total = 0;
  for (let i = 0; i < first14.length; i++) {
    const product = GST_CHARS.indexOf(first14[i]) * (i % 2 === 0 ? 1 : 2);
    total += Math.floor(product / 36) + (product % 36);
  }
  return GST_CHARS[(36 - (total % 36)) % 36];
}

export function validateGstin(v: string): string | null {
  const g = v.trim().toUpperCase();
  if (!/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(g)) {
    return "GSTIN must be 15 characters, e.g. 27AAPFU0939F1ZV";
  }
  const state = Number(g.slice(0, 2));
  if (!((state >= 1 && state <= 38) || state === 97 || state === 99)) return "GSTIN has an invalid state code";
  if (gstinCheckChar(g.slice(0, 14)) !== g[14]) return "This GSTIN's check digit is wrong — please re-check it";
  return null;
}

export function validatePan(v: string): string | null {
  return /^[A-Z]{5}[0-9]{4}[A-Z]$/.test(v.trim().toUpperCase()) ? null : "PAN must look like ABCDE1234F";
}

/** PAN is characters 3–12 of a GSTIN. */
export function panFromGstin(gstin: string): string {
  return gstin.trim().toUpperCase().slice(2, 12);
}

export type AddressValues = {
  label: string;
  recipient_name: string;
  phone: string;
  line1: string;
  line2: string;
  landmark: string;
  city: string;
  state: string;
  pincode: string;
};

export const EMPTY_ADDRESS: AddressValues = {
  label: "Home",
  recipient_name: "",
  phone: "",
  line1: "",
  line2: "",
  landmark: "",
  city: "",
  state: "",
  pincode: "",
};

/** First problem with an address, or null. `needRecipient` is false on the signup form (it reuses the account's name/mobile). */
export function validateAddress(a: AddressValues, needRecipient = true): string | null {
  if (needRecipient) {
    if (!a.recipient_name.trim()) return "Recipient name is required";
    const p = validatePhone(a.phone);
    if (p) return p;
  }
  if (!a.line1.trim()) return "Address line 1 is required";
  if (!a.city.trim()) return "City is required";
  if (!a.state) return "Select a state";
  return validatePincode(a.pincode);
}

type AddressLike = {
  recipient_name?: string | null;
  phone?: string | null;
  line1: string;
  line2?: string | null;
  landmark?: string | null;
  city: string;
  state?: string | null;
  pincode?: string | null;
};

/** Human-readable lines for showing a saved address (older addresses just lack the newer fields). */
export function addressLines(a: AddressLike): string[] {
  const street = [a.line1, a.line2, a.landmark].filter(Boolean).join(", ");
  const place = [a.city, a.state].filter(Boolean).join(", ") + (a.pincode ? ` - ${a.pincode}` : "");
  const who = [a.recipient_name, a.phone].filter(Boolean).join(" · ");
  return [who, street, place].filter(Boolean);
}
