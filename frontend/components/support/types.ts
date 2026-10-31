export type CaseKind = "order_problem" | "payment_problem" | "shop_report" | "general";
export type Audience = "customer" | "shop" | "admin";

export type CaseEvent = { id: string; kind: string; actor: string; note: string | null; created_at: string };

export type CustomerStats = {
  cases_total: number;
  ruled_against_60d: number;
  suggest_flag: boolean;
  flagged_at: string | null;
  flag_note: string | null;
};

// Mirrors backend SupportCaseOut. The server decides what each audience can
// see and do (the can_* flags); the UI only follows.
export type SupportCase = {
  id: string;
  kind: CaseKind;
  kind_label: string;
  status: "open" | "needs_info" | "shop_replied" | "escalated" | "action_pending" | "resolved";
  reason: string;
  reason_label: string;
  description: string;
  photos: string[];
  resolution: string | null;
  order_id: string | null;
  order_ref: string | null;
  order_status: string | null;
  order_total: string | null;
  shop_id: string | null;
  shop_name: string | null;
  customer_name: string | null;
  customer_id: string | null; // admin only
  shop_due_at: string | null;
  overdue: boolean;
  auto_close_at: string | null;
  info_request_text: string | null;
  info_requested_at: string | null;
  info_reply_text: string | null;
  info_reply_photos: string[];
  info_replied_at: string | null;
  shop_response_type: string | null;
  shop_response_label: string | null;
  shop_response_text: string | null;
  shop_response_photos: string[];
  shop_responded_at: string | null;
  escalated_at: string | null;
  escalation_note: string | null;
  ruling: string | null;
  ruling_label: string | null;
  ruling_note: string | null;
  ruled_at: string | null;
  order_action: string | null;
  order_action_note: string | null;
  order_action_deadline: string | null;
  order_action_done_at: string | null;
  action_overdue: boolean;
  review_outcome: string | null;
  internal_note: string | null;
  customer_stats: CustomerStats | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  can_accept: boolean;
  can_escalate: boolean;
  can_reply_info: boolean;
  can_reply: boolean;
  can_request_info: boolean;
  can_mark_action_done: boolean;
  can_rule: boolean;
  can_review: boolean;
  events: CaseEvent[];
};

export type SupportOptions = {
  kinds: { code: CaseKind; label: string }[];
  reasons: Record<CaseKind, { code: string; label: string }[]>;
  report_window_days: number;
  shop_reply_hours: number;
  auto_close_days: number;
  max_photos: number;
};

export function statusMeta(c: SupportCase, audience: Audience): { label: string; className: string } {
  const amber = "bg-amber-50 text-amber-700";
  const blue = "bg-blue-50 text-blue-700";
  const green = "bg-emerald-50 text-emerald-700";
  const red = "bg-red-50 text-red-700";
  switch (c.status) {
    case "open":
      if (audience !== "customer" && c.overdue) return { label: "Reply overdue", className: red };
      return { label: audience === "shop" ? "Needs your reply" : "Waiting for the shop", className: amber };
    case "needs_info":
      return { label: audience === "customer" ? "The shop needs more info" : "Waiting for the customer", className: amber };
    case "shop_replied":
      return { label: audience === "customer" ? "Shop replied" : "Waiting for the customer", className: blue };
    case "escalated":
      return { label: "With LocalMart support", className: blue };
    case "action_pending":
      if (audience !== "customer" && c.action_overdue) return { label: "Ordered action overdue", className: red };
      return { label: c.order_action === "refund" ? "Refund ordered" : "Resend ordered", className: amber };
    default:
      return { label: "Resolved", className: green };
  }
}

export function fmt(dt: string | null | undefined): string {
  if (!dt) return "";
  return new Date(dt).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

export function fmtDate(dt: string | null | undefined): string {
  if (!dt) return "";
  return new Date(dt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export const EVENT_LABEL: Record<string, string> = {
  opened: "Report filed",
  shop_replied: "Shop replied",
  info_requested: "Shop asked for more information",
  info_provided: "Customer added information",
  escalated: "Escalated to LocalMart support",
  overdue_flagged: "Flagged: no shop reply in time",
  ruled: "LocalMart support ruled",
  action_done: "Refund/resend confirmed",
  action_overdue: "Ordered action is overdue",
  accepted: "Closed by the customer",
  auto_closed: "Closed automatically",
  reviewed: "Reviewed by LocalMart support",
  shop_warned: "Shop warned",
  shop_hidden: "Shop hidden",
  owner_suspended: "Owner account suspended",
  flag_suggested: "Suggested flagging this customer",
};

export const ORDER_ACTION_LABEL: Record<string, string> = { refund: "Refund the customer", resend: "Resend the order" };

/** apiFetch throws `API error 409 [request_id=…]: {"detail":"…"}` — show just the detail. */
export function errorMessage(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  const body = raw.slice(raw.indexOf("]: ") + 3);
  try {
    const parsed = JSON.parse(body);
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail) && parsed.detail[0]?.msg) return String(parsed.detail[0].msg).replace(/^Value error, /, "");
  } catch {
    /* not JSON */
  }
  return raw.startsWith("API error") ? "Something went wrong. Please try again." : raw;
}

/** Still inside the window for reporting a problem? (The server enforces it too.) */
export function withinReportWindow(deliveredAt: string | null | undefined, days: number): boolean {
  if (!deliveredAt) return true;
  return Date.now() <= new Date(deliveredAt).getTime() + days * 24 * 3600 * 1000;
}
