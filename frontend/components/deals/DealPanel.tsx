"use client";

import { useEffect, useState } from "react";
import { Check, CircleDollarSign, Copy, ExternalLink, FileText, Handshake, History, MessageSquareReply, NotebookPen, Sparkles, Trash2 } from "lucide-react";
import { SheetContent, SheetTitle } from "@/components/ui/sheet";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Field, Input, NumberInput, TextArea } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { SectionHeader, StatStrip, StatTile } from "@/components/ui/stat";
import { btn, btnPrimary } from "@/lib/ui";
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

const VERDICT: Record<string, { label: string; tone: "good" | "warn" | "bad" }> = {
  great: { label: "Good price", tone: "good" },
  accept: { label: "Fair, accept", tone: "good" },
  counter: { label: "Counter", tone: "warn" },
  walk_away: { label: "Too high", tone: "bad" },
};
const ANGLE: Record<string, string> = {
  accept: "Accept their price",
  budget: "Counter with your budget",
  performance: "Lower fee + commission",
  scope: "Their price, smaller scope",
};

const opts = <T extends string>(list: readonly (readonly [T, string])[]) => list.map(([value, label]) => ({ value, label }));

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
  const views = deal.typical_views ? `Usually ${Math.round(deal.typical_views / 100) / 10}k views` : null;

  return (
    <SheetContent className="sm:max-w-[520px] bg-white dark:bg-[#0c0d0e] border-l border-zinc-200/80 dark:border-zinc-800/80 p-0 flex flex-col h-full text-zinc-700 dark:text-zinc-300">
      {/* header, the same as the creator panel's */}
      <div className="p-5 border-b border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50 dark:bg-[#08090a] flex items-center gap-3 pr-12">
        <CreatorAvatar
          name={deal.name}
          src={deal.avatar_url}
          className="w-10 h-10 rounded bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-300 dark:border-zinc-700/50 flex items-center justify-center shrink-0"
          textClassName="text-sm font-medium text-zinc-600 dark:text-zinc-400"
        />
        <div className="min-w-0 flex-1 space-y-1">
          <SheetTitle className="text-[15px] font-semibold text-zinc-900 dark:text-zinc-100 truncate leading-tight">
            {deal.url ? (
              <a href={deal.url} target="_blank" rel="noopener noreferrer" className="hover:underline underline-offset-4 decoration-zinc-300 dark:decoration-zinc-600">{deal.name}</a>
            ) : deal.name}
          </SheetTitle>
          <p className="text-[11px] text-zinc-500 truncate">{[views, deal.forecast].filter(Boolean).join(" · ") || "Deal"}</p>
        </div>
        <div className="w-[132px] shrink-0">
          <Select<Stage> label="Stage" value={deal.stage} onChange={(s) => save({ stage: s })} options={STAGES.map((s) => ({ value: s, label: STAGE_LABEL[s] }))} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-7">
        {error && <p className="text-xs text-rose-500">{error}</p>}

        {/* price */}
        <section className="space-y-3">
          <SectionHeader icon={<CircleDollarSign size={14} className="text-zinc-400" />}>Price</SectionHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Their quote"><NumberInput prefix="$" value={deal.quoted_rate} onSave={(v) => save({ quoted_rate: v })} placeholder="0" /></Field>
            <Field label="Agreed price"><NumberInput prefix="$" value={deal.agreed_rate} onSave={(v) => save({ agreed_rate: v })} placeholder="0" /></Field>
          </div>
          {a.fair_high != null && (
            <StatStrip cols={2}>
              <StatTile
                label="Fair for this deal"
                value={<span className="font-mono">{money(a.fair_low)}–{money(a.fair_high)}</span>}
                help="Worked out from their usual views and this deal's terms (format, usage rights, exclusivity)."
              />
              <StatTile
                label="Our read"
                value={verdict ? <>{verdict.label}{a.counter && a.verdict !== "accept" ? <span className="font-mono"> · {money(a.counter)}</span> : null}</> : "Waiting for their quote"}
                tone={verdict?.tone}
                sub={a.verdict ? a.reason : "Enter their quote above"}
                help={a.verdict ? a.reason : "Once you enter their quote, we compare it with the fair price."}
              />
            </StatStrip>
          )}
        </section>

        {/* reply helper */}
        {negotiating && (
          <section className="space-y-3">
            <SectionHeader icon={<MessageSquareReply size={14} className="text-zinc-400" />}>Reply to them</SectionHeader>
            {deal.quoted_rate == null || a.fair_high == null ? (
              <p className="text-xs text-zinc-500 leading-relaxed">
                {a.fair_high == null
                  ? "We don't have their usual views yet, so we can't suggest a reply."
                  : "Enter their quote under Price. We'll check it against the fair price and write a reply you can send."}
              </p>
            ) : (
              <>
                <TextArea value={reply} onSave={(v) => setReply(v ?? "")} rows={3} maxLength={3000} placeholder="Paste their message (optional). We read it to choose the best way to answer." />
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => getMessage(false)} disabled={!!busy} className={btn}>
                    <FileText size={13} /> {busy === "template" ? "Writing…" : "Write reply"}
                  </button>
                  <button type="button" onClick={() => getMessage(true)} disabled={!!busy} className={btn}>
                    <Sparkles size={13} className="text-violet-500" /> {busy === "ai" ? "Rewriting…" : "Rewrite with AI"}
                  </button>
                </div>
                {counter && (
                  <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                    <div className="flex items-center justify-between gap-2 px-3 py-1.5 bg-zinc-100 dark:bg-[#121314] border-b border-zinc-200 dark:border-zinc-800">
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
                <p className="text-[11px] text-zinc-500 leading-relaxed">
                  The price in the reply is worked out in code. Jev reads their message; AI only changes the wording, and we check the numbers didn&apos;t change.
                </p>
              </>
            )}
          </section>
        )}

        {/* terms */}
        <section className="space-y-3">
          <SectionHeader icon={<Handshake size={14} className="text-zinc-400" />}>What you agreed</SectionHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Deliverable">
              <Select label="Deliverable" value={deal.deliverable} onChange={(v) => save({ deliverable: v })} options={opts(DELIVERABLES)} />
            </Field>
            <Field label="Post by">
              <Input type="date" value={deal.post_by} onSave={(v) => save({ post_by: v })} />
            </Field>
            <Field label="Deal type">
              <Select label="Deal type" value={deal.deal_type} onChange={(v) => save({ deal_type: v })} options={opts(DEAL_TYPES)} />
            </Field>
            {(deal.deal_type === "base_plus_commission" || deal.deal_type === "affiliate") && (
              <Field label="Commission (%)">
                <NumberInput value={deal.commission_pct} onSave={(v) => save({ commission_pct: v })} placeholder="10" />
              </Field>
            )}
            <Field label="Usage rights">
              <Select label="Usage rights" value={deal.usage_rights} onChange={(v) => save({ usage_rights: v })} options={opts(USAGE)} />
            </Field>
            <Field label="Exclusivity (days)">
              <NumberInput value={deal.exclusivity_days || null} onSave={(v) => save({ exclusivity_days: Math.round(v ?? 0) })} placeholder="None" />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-xs text-zinc-700 dark:text-zinc-300">
            <input type="checkbox" checked={deal.disclosure} onChange={(e) => save({ disclosure: e.target.checked })} className="accent-zinc-900 dark:accent-zinc-100" />
            They label it as an ad (#ad or &ldquo;paid partnership&rdquo;)
          </label>
        </section>

        {/* proof & payment */}
        <section className="space-y-3">
          <SectionHeader icon={<ExternalLink size={14} className="text-zinc-400" />}>Live post and payment</SectionHeader>
          <Field label="Link to the live post">
            <div className="flex gap-2">
              <div className="flex-1 min-w-0">
                <Input type="url" inputMode="url" value={deal.post_url} onSave={(v) => save({ post_url: v })} placeholder="https://youtube.com/watch?v=…" />
              </div>
              {deal.post_url && (
                <a href={deal.post_url} target="_blank" rel="noopener noreferrer" aria-label="Open the post" className={`${btn} w-[30px] px-0`}><ExternalLink size={13} /></a>
              )}
            </div>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount paid">
              <NumberInput prefix="$" value={deal.paid_amount} onSave={(v) => save({ paid_amount: v })} placeholder={deal.agreed_rate ? String(deal.agreed_rate) : "0"} />
            </Field>
            <Field label="Payment reference">
              <Input value={deal.payment_ref} onSave={(v) => save({ payment_ref: v })} placeholder="UPI, PayPal or invoice no." />
            </Field>
          </div>
          {deal.stage !== "paid" ? (
            <button type="button" onClick={() => save({ stage: "paid" })} className={btnPrimary}>
              <Handshake size={13} /> Mark paid{deal.agreed_rate ? ` (${money(deal.paid_amount ?? deal.agreed_rate)})` : ""}
            </button>
          ) : (
            <p className="text-xs text-emerald-600 dark:text-emerald-400">Paid {money(deal.paid_amount)}{deal.paid_at ? ` · ${new Date(deal.paid_at).toLocaleDateString()}` : ""}</p>
          )}
        </section>

        {/* notes */}
        <section className="space-y-3">
          <SectionHeader icon={<NotebookPen size={14} className="text-zinc-400" />}>Notes</SectionHeader>
          <TextArea value={deal.notes} onSave={(v) => save({ notes: v })} placeholder="Anything to remember" />
        </section>

        {/* timeline */}
        {events.length > 0 && (
          <section className="space-y-3">
            <SectionHeader icon={<History size={14} className="text-zinc-400" />}>Timeline</SectionHeader>
            <ol className="space-y-1.5 border-l border-zinc-200 dark:border-zinc-800 pl-3">
              {events.map((e, i) => (
                <li key={i} className="text-xs flex justify-between gap-3">
                  <span className="text-zinc-700 dark:text-zinc-300">{eventText(e)}</span>
                  <span className="text-[11px] text-zinc-500 shrink-0">{e.at ? updatedLabel(e.at) : ""}</span>
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
