export const DOCUMENT_TYPES: { value: string; label: string }[] = [
  { value: "gst_certificate", label: "GST Certificate" },
  { value: "license", label: "Business / Trade License" },
  { value: "id_proof", label: "Owner ID Proof (Aadhaar / PAN / Passport)" },
  { value: "address_proof", label: "Business Address Proof" },
  { value: "other", label: "Other" },
];

export function documentTypeLabel(value: string): string {
  return DOCUMENT_TYPES.find((d) => d.value === value)?.label ?? value;
}
