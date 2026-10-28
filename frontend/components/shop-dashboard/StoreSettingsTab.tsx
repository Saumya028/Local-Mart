"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import {
  DAY_KEYS,
  DAY_LABELS,
  DayKey,
  HoursRange,
  OpeningHours,
  emptyHours,
  isFullDay,
} from "@/lib/shopInfo";
import { ShopStatusBadge } from "@/components/shop/ShopStatusBadge";
import { Shop } from "./types";

const SLOT_LENGTHS = [15, 30, 45, 60, 90, 120, 180, 240];
const input =
  "w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400";
const card = "bg-white border border-gray-100 rounded-2xl p-5 space-y-4";

// Starting point when an owner first turns hours on: a normal shop week.
function starterHours(): OpeningHours {
  const h = emptyHours();
  for (const d of DAY_KEYS) h[d] = d === "sun" ? [] : [{ open: "09:00", close: "21:00" }];
  return h;
}

function pad(n: number) {
  return String(n).padStart(2, "0");
}
function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className={card}>
      <div>
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-gray-600">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="block text-[11px] text-gray-400 mt-1">{hint}</span>}
    </label>
  );
}

function DayRow({
  day,
  ranges,
  onChange,
}: {
  day: DayKey;
  ranges: HoursRange[];
  onChange: (next: HoursRange[]) => void;
}) {
  const closed = ranges.length === 0;
  const full = isFullDay(ranges);
  const mode = closed ? "closed" : full ? "24h" : "custom";

  return (
    <div className="flex flex-wrap items-start gap-x-4 gap-y-2 py-2 border-b border-gray-50 last:border-0">
      <p className="w-24 text-sm text-gray-700 pt-1.5">{DAY_LABELS[day]}</p>
      <div className="flex-1 min-w-[16rem] space-y-2">
        <div className="flex gap-1.5 text-xs">
          {(
            [
              ["closed", "Closed"],
              ["24h", "Open 24 hours"],
              ["custom", "Set hours"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                if (key === "closed") onChange([]);
                else if (key === "24h") onChange([{ open: "00:00", close: "24:00" }]);
                else if (mode !== "custom") onChange([{ open: "09:00", close: "21:00" }]);
              }}
              className={`px-2.5 py-1 rounded-full border ${
                mode === key ? "bg-blue-600 border-blue-600 text-white" : "border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "custom" && (
          <div className="space-y-1.5">
            {ranges.map((r, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="time"
                  value={r.open}
                  onChange={(e) => onChange(ranges.map((x, j) => (j === i ? { ...x, open: e.target.value } : x)))}
                  className="border border-gray-200 rounded-md px-2 py-1 text-sm"
                  aria-label={`${DAY_LABELS[day]} opens`}
                />
                <span className="text-xs text-gray-400">to</span>
                <input
                  type="time"
                  value={r.close === "24:00" ? "23:59" : r.close}
                  onChange={(e) => onChange(ranges.map((x, j) => (j === i ? { ...x, close: e.target.value } : x)))}
                  className="border border-gray-200 rounded-md px-2 py-1 text-sm"
                  aria-label={`${DAY_LABELS[day]} closes`}
                />
                {r.close <= r.open && r.close !== "24:00" && <span className="text-[11px] text-amber-600">next day</span>}
                <button
                  type="button"
                  onClick={() => onChange(ranges.filter((_, j) => j !== i))}
                  className="text-xs text-gray-400 hover:text-red-500"
                  aria-label="Remove time range"
                >
                  ✕
                </button>
              </div>
            ))}
            {ranges.length < 3 && (
              <button
                type="button"
                onClick={() => onChange([...ranges, { open: "16:00", close: "21:00" }])}
                className="text-xs text-blue-600 hover:underline"
              >
                + Add another time range (e.g. after a lunch break)
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Owner-only: everything customers see about HOW and WHEN the shop operates —
 * contact details, opening hours, a vacation switch, delivery pricing and
 * timing/time slots. Saved through PUT /dashboard/shops/{id}.
 */
export function StoreSettingsTab({ shop, onSaved }: { shop: Shop; onSaved: (updated: Shop) => void }) {
  const [phone, setPhone] = useState(shop.contact_phone ?? "");
  const [about, setAbout] = useState(shop.description ?? "");

  const [hoursOn, setHoursOn] = useState(!!shop.opening_hours);
  const [hours, setHours] = useState<OpeningHours>(shop.opening_hours ?? starterHours());

  const [closedOn, setClosedOn] = useState(!!shop.temporarily_closed);
  const [closedMsg, setClosedMsg] = useState(shop.closed_message ?? "");
  const [closedUntil, setClosedUntil] = useState(toLocalInput(shop.closed_until));

  const [fee, setFee] = useState(String(shop.delivery_fee ?? "0"));
  const [freeAbove, setFreeAbove] = useState(shop.free_delivery_above != null ? String(shop.free_delivery_above) : "");
  const [minOrder, setMinOrder] = useState(String(shop.min_order_amount ?? "0"));

  const [prep, setPrep] = useState(String(shop.prep_time_minutes ?? 30));
  const [deliv, setDeliv] = useState(String(shop.delivery_time_minutes ?? 30));
  const [slotsOn, setSlotsOn] = useState(!!shop.slots_enabled);
  const [slotLen, setSlotLen] = useState(String(shop.slot_length_minutes ?? 60));
  const [capacity, setCapacity] = useState(String(shop.slot_capacity ?? 5));
  const [daysAhead, setDaysAhead] = useState(String(shop.slot_days_ahead ?? 2));

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const feeNum = Number(fee || 0);

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload: Record<string, unknown> = {
        description: about,
        opening_hours: hoursOn ? hours : null,
        temporarily_closed: closedOn,
        closed_message: closedOn ? closedMsg || null : null,
        closed_until: closedOn && closedUntil ? new Date(closedUntil).toISOString() : null,
        delivery_fee: fee || "0",
        free_delivery_above: freeAbove ? freeAbove : null,
        min_order_amount: minOrder || "0",
        prep_time_minutes: Number(prep || 0),
        delivery_time_minutes: Number(deliv || 0),
        slots_enabled: hoursOn && slotsOn,
        slot_length_minutes: Number(slotLen),
        slot_capacity: Number(capacity || 1),
        slot_days_ahead: Number(daysAhead || 1),
      };
      // Only send the phone when there is one: a shop created before phone numbers
      // existed can still save its other settings, and a number can't be cleared.
      if (phone.trim()) payload.contact_phone = phone;
      const updated: Shop = await apiFetch(`/dashboard/shops/${shop.id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      onSaved(updated);
      setHoursOn(!!updated.opening_hours);
      setSlotsOn(!!updated.slots_enabled);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="p-6 max-w-3xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Store settings</h1>
          <p className="text-sm text-gray-500">What customers see about when and how you serve them.</p>
        </div>
        <ShopStatusBadge info={shop.open_info} timezone={shop.timezone} />
      </div>

      <Section title="Contact & about">
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Contact phone" hint="Shown to customers so they can call you about an order.">
            <input
              type="tel"
              inputMode="tel"
              placeholder="98200 12345"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className={input}
            />
          </Field>
        </div>
        {!shop.contact_phone && !phone.trim() && (
          <p className="text-xs bg-amber-50 border border-amber-100 text-amber-800 rounded-md px-3 py-2">
            Add a contact number — customers with a question about their order have no way to reach you yet.
          </p>
        )}
        <Field label="About your shop" hint="A line or two: what you sell, how long you’ve been around (max 1000 characters).">
          <textarea value={about} onChange={(e) => setAbout(e.target.value)} rows={3} maxLength={1000} className={input} />
        </Field>
      </Section>

      <Section
        title="Opening hours"
        hint="Customers can only place an order while you’re open (or for a time slot, if you turn those on). Times are in India time."
      >
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={hoursOn} onChange={(e) => setHoursOn(e.target.checked)} />
          Set my opening hours
        </label>
        {!hoursOn && (
          <p className="text-xs text-gray-500">
            No hours set: your shop is treated as always open. Turn this on so customers can’t order when you’ve shut.
          </p>
        )}
        {hoursOn && (
          <div>
            {DAY_KEYS.map((d) => (
              <DayRow key={d} day={d} ranges={hours[d]} onChange={(next) => setHours((h) => ({ ...h, [d]: next }))} />
            ))}
            <button
              type="button"
              onClick={() => setHours((h) => {
                const next = { ...h };
                for (const d of DAY_KEYS) next[d] = h.mon.map((r) => ({ ...r }));
                return next;
              })}
              className="mt-3 text-xs text-blue-600 hover:underline"
            >
              Copy Monday’s hours to every day
            </button>
            <p className="text-[11px] text-gray-400 mt-2">
              A closing time earlier than the opening time means you stay open past midnight (e.g. 6:00 PM → 2:00 AM).
            </p>
          </div>
        )}
      </Section>

      <Section
        title="Temporarily closed"
        hint="Going away, a festival, a power cut? Customers still see your shop but can’t order until you reopen."
      >
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={closedOn} onChange={(e) => setClosedOn(e.target.checked)} />
          Shop is temporarily closed
        </label>
        {closedOn && (
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Message for customers (optional)">
              <input value={closedMsg} onChange={(e) => setClosedMsg(e.target.value)} maxLength={140} placeholder="Back after Diwali" className={input} />
            </Field>
            <Field label="Reopens automatically at (optional)" hint="Leave empty to stay closed until you untick this.">
              <input type="datetime-local" value={closedUntil} onChange={(e) => setClosedUntil(e.target.value)} className={input} />
            </Field>
          </div>
        )}
      </Section>

      <Section
        title="Delivery pricing"
        hint="Applies to delivery orders only — pickup is always free and has no minimum."
      >
        <div className="grid sm:grid-cols-3 gap-4">
          <Field label="Delivery fee (₹)" hint="0 = free delivery">
            <input type="number" min="0" max="5000" step="1" value={fee} onChange={(e) => setFee(e.target.value)} className={input} />
          </Field>
          <Field label="Free delivery above (₹)" hint="Optional. Orders at or above this skip the fee.">
            <input
              type="number" min="0" step="1" value={freeAbove} onChange={(e) => setFreeAbove(e.target.value)}
              disabled={feeNum <= 0} placeholder={feeNum <= 0 ? "Not needed" : "e.g. 500"} className={input}
            />
          </Field>
          <Field label="Minimum order (₹)" hint="0 = no minimum. Items only, before the fee.">
            <input type="number" min="0" step="1" value={minOrder} onChange={(e) => setMinOrder(e.target.value)} className={input} />
          </Field>
        </div>
      </Section>

      <Section
        title="Timing"
        hint="Used for the “expected by” time customers see. You can still push an individual order’s time back from the Orders tab."
      >
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Time to prepare an order (minutes)">
            <input type="number" min="0" max="720" value={prep} onChange={(e) => setPrep(e.target.value)} className={input} />
          </Field>
          <Field label="Delivery time after it’s ready (minutes)">
            <input type="number" min="0" max="720" value={deliv} onChange={(e) => setDeliv(e.target.value)} className={input} />
          </Field>
        </div>

        <div className="border-t border-gray-100 pt-4 space-y-3">
          <label className={`flex items-center gap-2 text-sm ${hoursOn ? "cursor-pointer" : "opacity-60"}`}>
            <input type="checkbox" checked={hoursOn && slotsOn} disabled={!hoursOn} onChange={(e) => setSlotsOn(e.target.checked)} />
            Let customers choose a delivery / pickup time slot
          </label>
          {!hoursOn && <p className="text-xs text-gray-500">Set your opening hours above first — slots are built from them.</p>}
          {hoursOn && slotsOn && (
            <div className="grid sm:grid-cols-3 gap-4">
              <Field label="Slot length">
                <select value={slotLen} onChange={(e) => setSlotLen(e.target.value)} className={input}>
                  {SLOT_LENGTHS.map((m) => (
                    <option key={m} value={m}>{m >= 60 && m % 60 === 0 ? `${m / 60} hour${m === 60 ? "" : "s"}` : `${m} minutes`}</option>
                  ))}
                </select>
              </Field>
              <Field label="Orders per slot" hint="Max orders you can handle in one slot.">
                <input type="number" min="1" max="500" value={capacity} onChange={(e) => setCapacity(e.target.value)} className={input} />
              </Field>
              <Field label="Book up to" hint="Counting today.">
                <select value={daysAhead} onChange={(e) => setDaysAhead(e.target.value)} className={input}>
                  {[1, 2, 3, 5, 7].map((d) => (
                    <option key={d} value={d}>{d === 1 ? "today only" : `${d} days`}</option>
                  ))}
                </select>
              </Field>
            </div>
          )}
          {hoursOn && slotsOn && (
            <p className="text-[11px] text-gray-400">
              Slots start no sooner than your preparation{" "}
              {`(+ delivery) time from now, and only inside your opening hours.`}
            </p>
          )}
        </div>
      </Section>

      {error && <p className="text-sm text-red-500">{error}</p>}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md px-5 py-2 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
        {saved && <span className="text-sm text-emerald-600">Saved ✓</span>}
      </div>
    </form>
  );
}
