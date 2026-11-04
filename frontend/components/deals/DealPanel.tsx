"use client";

import { useEffect, useState } from "react";
import { Check, Copy, ExternalLink, Handshake, Sparkles, Trash2 } from "lucide-react";
import { SheetContent, SheetTitle } from "@/components/ui/sheet";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import {
  type CounterOut,
  type Deal,
  type DealEvent,
  DEAL_TYPES,
  DELIVERABLES,
  STAGES,
  STAGE_LABEL,
  type Stage,
  USAGE,
  money,
} from "@/data/deals";
import { updatedLabel } from "@/types/campaign";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

const FIELD = "w-full h-8 px-2.5 text-[13px] rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600";
const LABEL = "text-[11px] font-medium text-zinc-500";
const H = "text-[11px] font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider";

const VERDICT: Record<string, { label: string; tone: string }> = {
  great: { label: "Good price", tone: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  accept: { label: "Fair, accept", tone: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  counter: { label: "Counter", tone: "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20" },
  walk_away: { label: "Too high", tone: "text-rose-500 bg-rose-500/10 border-rose-500/20" },
};
const ANGLE: Record<string, string> = {
  accept: "Accept their price",
  budget: "Counter with your budget",
  performance: "Lower fee + commission",
  scope: "Their price, smaller scope",
};

function eventText(e: DealEvent): string {
  const p = (e.payload || {}) as Record<string, unknown>;
  switch (e.type) {
    case "created":
      return "Added to deals";
    case "stage":
      return `Moved to ${STAGE_LABEL[(p.to as Stage) ?? "contacted"] ?? p.to}`;
    case "quoted_rate":
      return `Their quote: ${money(p.to as number)}`;
    case "agreed_rate":
      return `Agreed price: ${money(p.to as number)}`;
    case "post_url":
      return "Live post link added";
    case "paid":
      return `Marked paid${p.amount ? ` (${money(p.amount as number)})` : ""}`;
    default:
      return e.type;
  }
}

/** Number field that saves when you leave it (empty = cleared). */
function NumberField({ value, onSave, placeholder, prefix = "$" }: { value: number | null; onSave: (v: number | null) => void; placeholder?: string; prefix?: string }) {
  const [v, setV] = useState(value == null ? "" : String(value));
  useEffect(() => setV(value == null ? "" : String(value)), [value]);
  return (
    <div className="relative">
      {prefix && <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[13px] text-zinc-400">{prefix}</span>}
      <input
        inputMode="decimal"
        value={v}
        placeholder={placeholder}
        onChange={(e) => setV(e.target.value.replace(/[^\d.]/g, ""))}
        onBlur={() => {
          const n = v === "" ? null : Number(v);
          if (n !== value && (n === null || Number.isFinite(n))) onSave(n);
        }}
        className={`${FIELD} ${prefix ? "pl-6" : ""}`}
      />
    </div>
  );
}

export function DealPanel({ deal, api, onChange, onRemove }: {
  deal: Deal;
  api: Api;
  onChange: (d: Deal) => void;
  onRemove: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<DealEvent[]>([]);
  const [reply, setReply] = useState("");
  const [counter, setCounter] = useState<CounterOut | null>(null);
  const [busy, setBusy] = useState<"template" | "ai" | null>(null);
  const [copied, setCopied] = useState(false);
  const [postUrl, setPostUrl] = useState(deal.post_url ?? "");
  const [notes, setNotes] = useState(deal.notes ?? "");
  const [ref, setRef] = useState(deal.payment_ref ?? "");

  useEffect(() => {
    setPostUrl(deal.post_url ?? "");
    setNotes(deal.notes ?? "");
    setRef(deal.payment_ref ?? "");
  }, [deal.id, deal.post_url, deal.notes, deal.payment_ref]);

  const loadEvents = () =>
    api(`/api/deals/${deal.id}/events`).then((r) => Array.isArray(r.data) && setEvents(r.data as DealEvent[])).catch(() => {});
  useEffect(() => {
    loadEvents();
    setCounter(null);
    setReply("");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [deal.id]);

  const save = async (patch: Record<string, unknown>) => {
    setError(null);
    try {
      const r = await api(`/api/deals/${deal.id}`, { method: "PATCH", data: patch });
      onChange(r.data as Deal);
      loadEvents();
      setCounter(null);
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Couldn't save that. Try again.");
    }
  };

  const getMessage = async (rewrite: boolean) => {
    setBusy(rewrite ? "ai" : "template");
    setError(null);
    try {
      const r = await api(`/api/deals/${deal.id}/counter`, { method: "POST", data: { creator_reply: reply || null, rewrite } });
      setCounter(r.data as CounterOut);
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Couldn't write the message.");
    } finally {
      setBusy(null);
    }
  };

  const a = deal.advice;
  const verdict = a.verdict ? VERDICT[a.verdict] : null;
  const negotiating = ["contacted", "negotiating"].includes(deal.stage);
  const signals = counter?.signals || {};
  const read = [
    signals.ignored ? "their message looked odd, so it was ignored" : null,
    (signals.open_to_negotiate as number) >= 0.6 ? "open to negotiating" : null,
    (signals.firm_price as number) >= 0.6 ? "says the price is firm" : null,
    (signals.wants_commission as number) >= 0.6 ? "open to commission" : null,
    (signals.mentions_usage as number) >= 0.6 ? "mentions usage/exclusivity" : null,
  ].filter(Boolean);

  return (
    <SheetContent className="sm:max-w-[520px] bg-white dark:bg-[#0c0d0e] border-l border-zinc-200/80 dark:border-zinc-800/80 p-0 flex flex-col h-full text-zinc-700 dark:text-zinc-300">
      {/* header */}
      <div className="p-5 border-b border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50 dark:bg-[#08090a] flex items-center gap-3 pr-12">
        <CreatorAvatar name={deal.name} src={deal.avatar_url} className="w-10 h-10 rounded border border-zinc-300 dark:border-zinc-700/50 bg-zinc-100 dark:bg-zinc-800/50 flex items-center justify-center shrink-0" textClassName="text-sm font-medium" />
        <div className="min-w-0 flex-1">
          <SheetTitle className="text-base font-semibold text-zinc-900 dark:text-zinc-100 truncate">
            {deal.url ? <a href={deal.url} target="_blank" rel="noopener noreferrer" className="hover:underline underline-offset-4">{deal.name}</a> : deal.name}
          </SheetTitle>
          <p className="text-[11px] text-zinc-500">{deal.typical_views ? `Usually ${Math.round(deal.typical_views / 100) / 10}k views` : "Deal"}{deal.forecast ? ` · ${deal.forecast}` : ""}</p>
        </div>
        <select value={deal.stage} onChange={(e) => save({ stage: e.target.value })} aria-label="Stage" className="h-8 px-2 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] text-zinc-900 dark:text-zinc-100">
          {STAGES.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
        </select>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {error && <p className="text-xs text-rose-500">{error}</p>}

        {/* price & negotiation */}
        <section className="space-y-3">
          <h3 className={H}>Price</h3>
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1"><span className={LABEL}>Their quote</span><NumberField value={deal.quoted_rate} onSave={(v) => save({ quoted_rate: v })} placeholder="0" /></label>
            <label className="space-y-1"><span className={LABEL}>Agreed price</span><NumberField value={deal.agreed_rate} onSave={(v) => save({ agreed_rate: v })} placeholder="0" /></label>
          </div>
          {a.fair_high != null && (
            <div className="rounded-md border border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-50 dark:bg-[#121314] p-3 space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-zinc-500">Fair for this deal <span className="font-mono text-zinc-900 dark:text-zinc-100">{money(a.fair_low)}–{money(a.fair_high)}</span></span>
                {verdict && <span className={`px-1.5 py-0.5 rounded border text-[10px] font-semibold ${verdict.tone}`}>{verdict.label}{a.counter && a.verdict !== "accept" ? ` · ${money(a.counter)}` : ""}</span>}
              </div>
              {a.verdict && <p className="text-[11px] text-zinc-500 leading-relaxed">{a.reason}</p>}
            </div>
          )}

          {negotiating && deal.quoted_rate != null && a.fair_high != null && (
            <div className="space-y-2">
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value.slice(0, 3000))}
                rows={2}
                placeholder="Paste their reply (optional): we'll read it to pick the best way to answer"
                aria-label="Their reply"
                className="w-full px-2.5 py-2 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent focus:outline-none focus:border-zinc-400 resize-none"
              />
              <div className="flex gap-2">
                <button type="button" onClick={() => getMessage(false)} disabled={!!busy} className="h-8 px-3 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50">
                  {busy === "template" ? "Writing…" : "Write reply"}
                </button>
                <button type="button" onClick={() => getMessage(true)} disabled={!!busy} className="h-8 px-3 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50 flex items-center gap-1.5">
                  <Sparkles size={12} className="text-violet-500" /> {busy === "ai" ? "Rewriting…" : "Rewrite with AI"}
                </button>
              </div>
              {counter && (
                <div className="rounded-md border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                  <div className="flex items-center justify-between gap-2 px-3 py-1.5 bg-zinc-50 dark:bg-[#121314] border-b border-zinc-200 dark:border-zinc-800">
                    <span className="text-[11px] text-zinc-500 truncate">
                      {ANGLE[counter.angle]}{read.length ? ` · ${read.join(", ")}` : ""}{counter.source === "ai" ? " · AI wording" : ""}
                    </span>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(counter.message);
                          setCopied(true);
                          setTimeout(() => setCopied(false), 1500);
                        } catch {}
                      }}
                      className="flex items-center gap-1 text-[11px] font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 shrink-0"
                    >
                      {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />} {copied ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <p className="p-3 text-[13px] whitespace-pre-wrap leading-relaxed text-zinc-800 dark:text-zinc-200">{counter.message}</p>
                </div>
              )}
            </div>
          )}
        </section>

        {/* terms */}
        <section className="space-y-3">
          <h3 className={H}>What was agreed</h3>
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1"><span className={LABEL}>Deliverable</span>
              <select value={deal.deliverable} onChange={(e) => save({ deliverable: e.target.value })} className={FIELD}>
                {DELIVERABLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="space-y-1"><span className={LABEL}>Post by</span>
              <input type="date" value={deal.post_by ?? ""} onChange={(e) => save({ post_by: e.target.value || null })} className={FIELD} />
            </label>
            <label className="space-y-1"><span className={LABEL}>Deal type</span>
              <select value={deal.deal_type} onChange={(e) => save({ deal_type: e.target.value })} className={FIELD}>
                {DEAL_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            {(deal.deal_type === "base_plus_commission" || deal.deal_type === "affiliate") && (
              <label className="space-y-1"><span className={LABEL}>Commission</span>
                <NumberField value={deal.commission_pct} onSave={(v) => save({ commission_pct: v })} prefix="%" />
              </label>
            )}
            <label className="space-y-1"><span className={LABEL}>Usage rights</span>
              <select value={deal.usage_rights} onChange={(e) => save({ usage_rights: e.target.value })} className={FIELD}>
                {USAGE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="space-y-1"><span className={LABEL}>Exclusivity (days)</span>
              <NumberField value={deal.exclusivity_days || null} onSave={(v) => save({ exclusivity_days: Math.round(v ?? 0) })} prefix="" placeholder="None" />
            </label>
          </div>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={deal.disclosure} onChange={(e) => save({ disclosure: e.target.checked })} className="accent-zinc-900 dark:accent-zinc-100" />
            They label it as an ad (#ad or &ldquo;paid partnership&rdquo;)
          </label>
        </section>

        {/* proof & payment */}
        <section className="space-y-3">
          <h3 className={H}>Live post & payment</h3>
          <label className="space-y-1 block"><span className={LABEL}>Link to the live post</span>
            <div className="flex gap-2">
              <input value={postUrl} onChange={(e) => setPostUrl(e.target.value)} onBlur={() => postUrl.trim() !== (deal.post_url ?? "") && save({ post_url: postUrl.trim() || null })} placeholder="https://youtube.com/watch?v=…" className={FIELD} />
              {deal.post_url && (
                <a href={deal.post_url} target="_blank" rel="noopener noreferrer" aria-label="Open the post" className="h-8 w-8 shrink-0 flex items-center justify-center rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800"><ExternalLink size={13} /></a>
              )}
            </div>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1"><span className={LABEL}>Amount paid</span><NumberField value={deal.paid_amount} onSave={(v) => save({ paid_amount: v })} placeholder={deal.agreed_rate ? String(deal.agreed_rate) : "0"} /></label>
            <label className="space-y-1"><span className={LABEL}>Payment reference</span>
              <input value={ref} onChange={(e) => setRef(e.target.value)} onBlur={() => ref !== (deal.payment_ref ?? "") && save({ payment_ref: ref || null })} placeholder="UPI / PayPal / invoice no." className={FIELD} />
            </label>
          </div>
          {deal.stage !== "paid" ? (
            <button type="button" onClick={() => save({ stage: "paid" })} className="h-8 px-3 text-xs font-medium rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 hover:opacity-90 flex items-center gap-1.5">
              <Handshake size={13} /> Mark paid{deal.agreed_rate ? ` (${money(deal.paid_amount ?? deal.agreed_rate)})` : ""}
            </button>
          ) : (
            <p className="text-xs text-emerald-600 dark:text-emerald-400">Paid {money(deal.paid_amount)}{deal.paid_at ? ` · ${new Date(deal.paid_at).toLocaleDateString()}` : ""}</p>
          )}
        </section>

        {/* notes */}
        <section className="space-y-2">
          <h3 className={H}>Notes</h3>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value.slice(0, 4000))} onBlur={() => notes !== (deal.notes ?? "") && save({ notes: notes || null })} rows={3} placeholder="Anything to remember" className="w-full px-2.5 py-2 text-[13px] rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent focus:outline-none focus:border-zinc-400 resize-none" />
        </section>

        {/* timeline */}
        {events.length > 0 && (
          <section className="space-y-2">
            <h3 className={H}>Timeline</h3>
            <ol className="space-y-1.5 border-l border-zinc-200 dark:border-zinc-800 pl-3">
              {events.map((e, i) => (
                <li key={i} className="text-xs flex justify-between gap-3">
                  <span className="text-zinc-700 dark:text-zinc-300">{eventText(e)}</span>
                  <span className="text-zinc-500 shrink-0">{e.at ? updatedLabel(e.at) : ""}</span>
                </li>
              ))}
            </ol>
          </section>
        )}

        <button type="button" onClick={onRemove} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-rose-500">
          <Trash2 size={12} /> Remove from deals
        </button>
      </div>
    </SheetContent>
  );
}
