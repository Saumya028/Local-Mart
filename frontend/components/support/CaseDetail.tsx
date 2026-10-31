"use client";

import { PhotoStrip } from "./EvidenceUploader";
import { Audience, EVENT_LABEL, ORDER_ACTION_LABEL, SupportCase, fmt, fmtDate, statusMeta } from "./types";

function Block({ title, children, tone = "gray" }: { title: string; children: React.ReactNode; tone?: "gray" | "blue" | "amber" | "green" }) {
  const tones = {
    gray: "bg-gray-50 border-gray-100",
    blue: "bg-blue-50/60 border-blue-100",
    amber: "bg-amber-50/70 border-amber-100",
    green: "bg-emerald-50/70 border-emerald-100",
  };
  return (
    <div className={`rounded-xl border px-4 py-3 space-y-1 ${tones[tone]}`}>
      <p className="text-xs font-semibold text-gray-500">{title}</p>
      <div className="text-sm text-gray-800 space-y-1">{children}</div>
    </div>
  );
}

/** Everything about one case, read-only. Actions live in each audience's tab. */
export function CaseDetail({ c, audience }: { c: SupportCase; audience: Audience }) {
  const meta = statusMeta(c, audience);
  const direct = c.kind === "shop_report" || c.kind === "general";
  const reporter = audience === "customer";
  const theirs = reporter ? "You" : audience === "shop" ? "The customer" : (c.customer_name ?? "Customer");

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-gray-900">{c.reason_label}</p>
          <p className="text-xs text-gray-400">
            {c.kind_label}
            {c.order_ref && <> · Order {c.order_ref}</>}
            {c.order_total && <> · {c.order_total}</>}
            {c.shop_name && audience !== "shop" && <> · {c.shop_name}</>}
            {audience !== "customer" && c.customer_name && <> · {c.customer_name}</>}
            {" · "}
            {fmt(c.created_at)}
          </p>
        </div>
        <span className={`text-xs font-medium rounded-full px-2.5 py-1 whitespace-nowrap ${meta.className}`}>{meta.label}</span>
      </div>

      <Block title={`${theirs} reported`}>
        <p className="whitespace-pre-wrap">{c.description}</p>
        <PhotoStrip photos={c.photos} />
      </Block>

      {c.info_request_text && (
        <Block title={reporter ? "The shop asked you" : "Information requested"} tone="amber">
          <p className="whitespace-pre-wrap">{c.info_request_text}</p>
          {c.info_reply_text && (
            <div className="pt-2 mt-2 border-t border-amber-100">
              <p className="text-xs font-semibold text-gray-500">{reporter ? "Your answer" : "Customer’s answer"}</p>
              <p className="whitespace-pre-wrap">{c.info_reply_text}</p>
              <PhotoStrip photos={c.info_reply_photos} />
            </div>
          )}
        </Block>
      )}

      {c.shop_response_type && (
        <Block title={`${audience === "shop" ? "Your reply" : "Shop’s reply"} · ${c.shop_response_label}`} tone="blue">
          <p className="whitespace-pre-wrap">{c.shop_response_text}</p>
          <PhotoStrip photos={c.shop_response_photos} />
        </Block>
      )}

      {c.escalated_at && !direct && (
        <Block title={`Escalated to LocalMart support · ${fmt(c.escalated_at)}`}>
          {c.escalation_note ? <p className="whitespace-pre-wrap">{c.escalation_note}</p> : <p className="text-gray-500">No extra note.</p>}
        </Block>
      )}

      {c.ruling && (
        <Block title={`LocalMart support ruled · ${c.ruling_label}`} tone="green">
          <p className="whitespace-pre-wrap">{c.ruling_note}</p>
          {c.order_action && (
            <p className="font-medium pt-1">
              {ORDER_ACTION_LABEL[c.order_action]}
              {c.order_action_deadline && !c.order_action_done_at && <> by {fmtDate(c.order_action_deadline)}</>}
              {c.order_action_done_at && <> — confirmed {fmtDate(c.order_action_done_at)}</>}
            </p>
          )}
          {c.order_action_note && <p className="text-gray-600">{c.order_action_note}</p>}
        </Block>
      )}

      {c.review_outcome && (
        <Block title="Reviewed by LocalMart support" tone="green">
          <p>{c.review_outcome === "action_taken" ? "Action was taken. Thanks for letting us know." : "No action was needed. Thanks for letting us know."}</p>
        </Block>
      )}

      {c.status === "resolved" && c.resolution === "auto_closed" && (
        <p className="text-xs text-gray-400">Closed automatically after no response. {fmtDate(c.resolved_at)}</p>
      )}
      {c.status === "resolved" && c.resolution === "accepted" && <p className="text-xs text-gray-400">Closed by the customer. {fmtDate(c.resolved_at)}</p>}

      {c.events.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-xs font-medium text-gray-500">History ({c.events.length})</summary>
          <ol className="relative border-l border-gray-200 ml-2 mt-3 space-y-3">
            {c.events.map((e) => (
              <li key={e.id} className="pl-4 relative">
                <span className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500" aria-hidden="true" />
                <p className="text-sm text-gray-900">{EVENT_LABEL[e.kind] ?? e.kind.replace(/_/g, " ")}</p>
                <p className="text-xs text-gray-400">
                  {e.actor} · {fmt(e.created_at)}
                </p>
                {e.note && <p className="text-xs text-gray-600 mt-0.5 whitespace-pre-wrap">{e.note}</p>}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
