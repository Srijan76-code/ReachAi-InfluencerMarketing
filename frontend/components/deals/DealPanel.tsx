"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ExternalLink, Loader2, Trash2 } from "lucide-react";
import { SheetContent, SheetTitle } from "@/components/ui/sheet";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Field, Input, NumberInput, TextArea } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { SectionHeader } from "@/components/ui/stat";
import { btn, btnPrimary, control, textarea } from "@/lib/ui";
import { ProposalCard } from "@/components/deals/NeedsYou";
import {
  type Deal,
  type DealEvent,
  DEAL_TYPES,
  DELIVERABLES,
  STAGES,
  STAGE_LABEL,
  type Proposal,
  type Stage,
  USAGE,
  money,
} from "@/data/deals";
import { updatedLabel } from "@/types/campaign";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

const VERDICT: Record<string, { label: string; tone: string }> = {
  great: { label: "a good price", tone: "text-emerald-600 dark:text-emerald-400" },
  accept: { label: "fair", tone: "text-emerald-600 dark:text-emerald-400" },
  counter: { label: "above fair", tone: "text-amber-600 dark:text-amber-400" },
  walk_away: { label: "far too high", tone: "text-rose-500" },
};

const label = <T extends string>(list: readonly (readonly [T, string])[], v: string) => list.find(([k]) => k === v)?.[1] ?? v;
const opts = <T extends string>(list: readonly (readonly [T, string])[]) => list.map(([value, l]) => ({ value, label: l }));

function errorText(e: unknown, fallback: string) {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

function eventText(e: DealEvent): string {
  const p = (e.payload || {}) as Record<string, unknown>;
  switch (e.type) {
    case "created":
      return "Added to deals";
    case "stage":
      return `Moved to ${STAGE_LABEL[(p.to as Stage) ?? "contacted"] ?? p.to}`;
    case "quoted_rate":
      return p.to == null ? "Their quote cleared" : `Their quote: ${money(p.to as number)}`;
    case "agreed_rate":
      return `Agreed price: ${money(p.to as number)}`;
    case "post_url":
      return "Live post link added";
    case "paid":
      return `Marked paid${p.amount ? ` (${money(p.amount as number)})` : ""}`;
    case "creator_reply":
      return "Their reply read";
    case "message_sent":
      return `Message sent${p.edited ? " (you edited it)" : ""}`;
    case "proposal":
      return `${p.decision === "skipped" ? "Skipped" : "Approved"}: ${p.title}`;
    default:
      return e.type;
  }
}

/** The negotiation so far: their asks and our offers, oldest first (numbers from the timeline). */
function negotiation(events: DealEvent[]): { who: "them" | "you"; text: string }[] {
  const out: { who: "them" | "you"; text: string }[] = [];
  for (const e of [...events].reverse()) {
    const p = (e.payload || {}) as Record<string, unknown>;
    if (e.type === "quoted_rate" && p.to != null) out.push({ who: "them", text: `Asked ${money(p.to as number)}` });
    if (e.type === "message_sent" && p.amounts) {
      const a = p.amounts as Record<string, number>;
      const offer = a.base ? `${money(a.base)} + ${a.commission_pct}% commission` : money(a.price ?? a.counter);
      out.push({ who: "you", text: `${a.price ? "Accepted" : "Offered"} ${offer}${p.final ? " (final)" : ""}` });
    }
  }
  return out;
}

/** Their quote: saved with a button (or Enter), so you always see when it's being checked. */
function QuoteField({ value, onSave }: { value: number | null; onSave: (v: number | null) => Promise<void> }) {
  const [v, setV] = useState(value == null ? "" : String(value));
  const [prev, setPrev] = useState(value);
  const [saving, setSaving] = useState(false);
  if (value !== prev) {
    setPrev(value);
    setV(value == null ? "" : String(value));
  }
  const parsed = v.trim() === "" ? null : Number(v.replace(/[^\d.]/g, ""));
  const dirty = parsed !== value && (parsed === null || Number.isFinite(parsed));
  const save = async () => {
    if (!dirty) return;
    setSaving(true);
    await onSave(parsed);
    setSaving(false);
  };
  return (
    <div className="flex gap-2">
      <div className="relative flex-1">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400 pointer-events-none">$</span>
        <input
          inputMode="decimal"
          value={v}
          onChange={(e) => setV(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()}
          placeholder="Their price"
          aria-label="Their quote"
          className={`${control} pl-6`}
        />
      </div>
      {(dirty || saving) && (
        <button type="button" onClick={save} disabled={saving} className={btnPrimary}>
          {saving ? <Loader2 size={13} className="animate-spin" /> : null} {saving ? "Checking" : "Save"}
        </button>
      )}
    </div>
  );
}

export function DealPanel({ deal, api, onChange, onRemove, proposals, onProposals }: {
  deal: Deal;
  api: Api;
  onChange: (d: Deal) => void;
  onRemove: () => void;
  proposals: Proposal[];
  onProposals: (data: { proposals?: Proposal[] }) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<DealEvent[]>([]);
  const [reply, setReply] = useState("");
  const [reading, setReading] = useState(false);
  const [read, setRead] = useState<string | null>(null);
  const [termsOpen, setTermsOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  const loadEvents = () =>
    api(`/api/deals/${deal.id}/events`).then((r) => Array.isArray(r.data) && setEvents(r.data as DealEvent[])).catch(() => {});
  useEffect(() => {
    loadEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [deal.id, deal.updated_at, proposals.length]);

  const save = async (patch: Record<string, unknown>) => {
    setError(null);
    try {
      const r = await api(`/api/deals/${deal.id}`, { method: "PATCH", data: patch });
      onChange(r.data as Deal); // the board reloads, which also refreshes the next step
    } catch (e) {
      setError(errorText(e, "Couldn't save that. Try again."));
    }
  };

  const readReply = async () => {
    setReading(true);
    setError(null);
    try {
      const r = (await api(`/api/deals/${deal.id}/reply`, { method: "POST", data: { text: reply } })).data as {
        signals: Record<string, number | boolean>;
        proposals: Proposal[];
      };
      const s = r.signals || {};
      const F = 0.6;
      const found = s.ignored
        ? ["it looked like it was written to instruct an AI, so we ignored it"]
        : [
            (s.declined as number) >= F ? "they're turning it down" : null,
            (s.agrees as number) >= F ? "they accept your offer" : null,
            (s.gives_price as number) >= F ? "they give a price" : null,
            (s.firm_price as number) >= F ? "their price is firm" : null,
            (s.wants_commission as number) >= F ? "open to commission" : null,
            (s.open_to_negotiate as number) >= F ? "open to negotiating" : null,
          ].filter((x): x is string => !!x);
      setRead(found.length ? `We read: ${found.join(", ")}.` : "Nothing in it changes the next step.");
      setReply("");
      onProposals(r);
    } catch (e) {
      setError(errorText(e, "Couldn't read their reply. Try again."));
    } finally {
      setReading(false);
    }
  };

  const a = deal.advice;
  const verdict = a.verdict ? VERDICT[a.verdict] : null;
  const talking = deal.stage === "contacted" || deal.stage === "negotiating";
  const posting = deal.stage === "agreed" || deal.stage === "content";
  const afterPost = deal.stage === "live" || deal.stage === "paid";
  const views = deal.typical_views ? `Usually ${Math.round(deal.typical_views / 100) / 10}k views` : null;
  const fair = a.fair_high != null ? `Fair ${money(a.fair_low)}–${money(a.fair_high)}` : null;
  const history = negotiation(events);
  const commission = deal.deal_type === "base_plus_commission" || deal.deal_type === "affiliate";
  const terms = [
    label(DELIVERABLES, deal.deliverable),
    label(DEAL_TYPES, deal.deal_type) + (commission && deal.commission_pct ? ` ${deal.commission_pct}%` : ""),
    label(USAGE, deal.usage_rights),
    deal.exclusivity_days ? `${deal.exclusivity_days} days exclusive` : null,
    deal.disclosure ? "#ad" : "No #ad",
  ].filter(Boolean).join(" · ");
  const status =
    deal.stage === "contacted" ? "Waiting for their reply."
    : deal.stage === "negotiating" ? "Waiting for their answer."
    : posting ? (deal.post_by ? `Waiting for the post, due ${new Date(deal.post_by + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })}.` : "Add a post-by date below so we can remind you if it's late.")
    : deal.stage === "live" ? "The post is live. Mark it paid once you've paid them."
    : deal.stage === "paid" ? `Paid ${money(deal.paid_amount)}${deal.paid_at ? ` on ${new Date(deal.paid_at).toLocaleDateString()}` : ""}.`
    : "This deal isn't going ahead.";

  return (
    <SheetContent className="sm:max-w-[480px] bg-white dark:bg-[#0c0d0e] border-l border-zinc-200/80 dark:border-zinc-800/80 p-0 flex flex-col h-full text-zinc-700 dark:text-zinc-300">
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
          <p className="text-[11px] text-zinc-500 truncate">{[views, fair].filter(Boolean).join(" · ") || "Deal"}</p>
        </div>
        <div className="w-[128px] shrink-0">
          <Select<Stage> label="Stage" value={deal.stage} onChange={(s) => save({ stage: s })} options={STAGES.map((s) => ({ value: s, label: STAGE_LABEL[s] }))} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {error && <p className="text-xs text-rose-500">{error}</p>}

        {/* next step: what to do now */}
        <section className="space-y-3">
          <SectionHeader>Next step</SectionHeader>
          {proposals.length > 0
            ? proposals.map((p) => <ProposalCard key={`${p.id}:${p.message}`} p={p} api={api} onDone={onProposals} />)
            : <p className="text-[13px] text-zinc-700 dark:text-zinc-300">{status}</p>}

          {talking && (
            <div className="space-y-2 pt-1">
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value.slice(0, 3000))}
                rows={3}
                aria-label="Their reply"
                placeholder="Did they reply? Paste it here"
                className={textarea}
              />
              <div className="flex items-center gap-3 min-w-0">
                <button type="button" onClick={readReply} disabled={reading || !reply.trim()} className={btn}>
                  {reading && <Loader2 size={13} className="animate-spin" />} {reading ? "Reading" : "Read reply"}
                </button>
                {read && <span className="text-[11px] text-zinc-500 truncate" title={read}>{read}</span>}
              </div>
            </div>
          )}
        </section>

        {/* price: only while you're talking price */}
        {talking && (
          <section className="space-y-3">
            <SectionHeader>Price</SectionHeader>
            <Field label="Their quote">
              <QuoteField value={deal.quoted_rate} onSave={(v) => save({ quoted_rate: v })} />
            </Field>
            {a.fair_high != null && (
              <p className="text-xs text-zinc-500 leading-relaxed">
                {deal.quoted_rate == null ? (
                  <>Fair for this deal: <span className="font-mono text-zinc-900 dark:text-zinc-100">{money(a.fair_low)}–{money(a.fair_high)}</span>. Enter their price when they tell you.</>
                ) : (
                  <>
                    <span className="font-mono text-zinc-900 dark:text-zinc-100">{money(deal.quoted_rate)}</span> is{" "}
                    <span className={`font-medium ${verdict?.tone ?? ""}`}>{verdict?.label ?? "—"}</span>
                    {" "}(fair <span className="font-mono">{money(a.fair_low)}–{money(a.fair_high)}</span>).
                  </>
                )}
              </p>
            )}
            {history.length > 0 && (
              <ol className="space-y-1">
                {history.map((h, i) => (
                  <li key={i} className="flex items-center gap-2 text-xs">
                    <span className={`w-10 shrink-0 text-[11px] ${h.who === "you" ? "text-zinc-900 dark:text-zinc-100 font-medium" : "text-zinc-500"}`}>{h.who === "you" ? "You" : "They"}</span>
                    <span className="text-zinc-700 dark:text-zinc-300">{h.text}</span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}

        {/* after agreeing: the price, and the post date when it's missing */}
        {!talking && deal.stage !== "lost" && (
          <section className="space-y-3">
            <SectionHeader>Agreed</SectionHeader>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Price">
                <NumberInput prefix="$" value={deal.agreed_rate} onSave={(v) => save({ agreed_rate: v })} placeholder="Agreed price" />
              </Field>
              <Field label="Post by">
                <Input type="date" value={deal.post_by} onSave={(v) => save({ post_by: v })} />
              </Field>
            </div>
          </section>
        )}

        {/* the post and payment, once it's being made */}
        {(posting || afterPost) && (
          <section className="space-y-3">
            <SectionHeader>{afterPost ? "Post and payment" : "Post"}</SectionHeader>
            <Field label="Link to the live post">
              <div className="flex gap-2">
                <div className="flex-1 min-w-0">
                  <Input type="url" inputMode="url" value={deal.post_url} onSave={(v) => save({ post_url: v })} placeholder="Paste it when it's up" />
                </div>
                {deal.post_url && (
                  <a href={deal.post_url} target="_blank" rel="noopener noreferrer" aria-label="Open the post" className={`${btn} w-[30px] px-0`}><ExternalLink size={13} /></a>
                )}
              </div>
            </Field>
            {afterPost && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Amount paid">
                  <NumberInput prefix="$" value={deal.paid_amount} onSave={(v) => save({ paid_amount: v })} placeholder={deal.agreed_rate ? String(deal.agreed_rate) : "Amount"} />
                </Field>
                <Field label="Payment reference">
                  <Input value={deal.payment_ref} onSave={(v) => save({ payment_ref: v })} placeholder="UPI, PayPal or invoice no." />
                </Field>
              </div>
            )}
          </section>
        )}

        {/* terms: prefilled, folded into one line */}
        <section className="space-y-3">
          <button type="button" onClick={() => setTermsOpen((v) => !v)} className="w-full flex items-center justify-between gap-3 text-left">
            <span className="min-w-0">
              <span className="block text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Terms</span>
              {!termsOpen && <span className="block text-[11px] text-zinc-500 truncate">{terms}</span>}
            </span>
            <span className="flex items-center gap-1 text-[11px] text-zinc-500 shrink-0">
              {termsOpen ? "Done" : "Edit"} <ChevronDown size={12} className={`transition-transform ${termsOpen ? "rotate-180" : ""}`} />
            </span>
          </button>
          {termsOpen && (
            <div className="space-y-3">
              <p className="text-[11px] text-zinc-500">Filled in with the usual choices for your goal. Change them if you agreed something else.</p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Deliverable">
                  <Select label="Deliverable" value={deal.deliverable} onChange={(v) => save({ deliverable: v })} options={opts(DELIVERABLES)} />
                </Field>
                <Field label="Deal type">
                  <Select label="Deal type" value={deal.deal_type} onChange={(v) => save({ deal_type: v })} options={opts(DEAL_TYPES)} />
                </Field>
                {commission && (
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
                {talking && (
                  <Field label="Post by">
                    <Input type="date" value={deal.post_by} onSave={(v) => save({ post_by: v })} />
                  </Field>
                )}
              </div>
              <label className="flex items-center gap-2 text-xs text-zinc-700 dark:text-zinc-300">
                <input type="checkbox" checked={deal.disclosure} onChange={(e) => save({ disclosure: e.target.checked })} className="accent-zinc-900 dark:accent-zinc-100" />
                They label it as an ad (#ad or &ldquo;paid partnership&rdquo;)
              </label>
            </div>
          )}
        </section>

        {/* notes, history, remove */}
        <section className="space-y-3 border-t border-zinc-200/60 dark:border-zinc-800/60 pt-4">
          <button type="button" onClick={() => setMoreOpen((v) => !v)} className="flex items-center gap-1 text-[12px] font-medium text-zinc-600 dark:text-zinc-400">
            Notes and history <ChevronDown size={12} className={`transition-transform ${moreOpen ? "rotate-180" : ""}`} />
          </button>
          {moreOpen && (
            <div className="space-y-4">
              <TextArea value={deal.notes} onSave={(v) => save({ notes: v })} placeholder="Notes" />
              {events.length > 0 && (
                <ol className="space-y-1.5 border-l border-zinc-200 dark:border-zinc-800 pl-3">
                  {events.map((e, i) => (
                    <li key={i} className="text-xs flex justify-between gap-3">
                      <span className="text-zinc-700 dark:text-zinc-300">{eventText(e)}</span>
                      <span className="text-[11px] text-zinc-500 shrink-0">{e.at ? updatedLabel(e.at) : ""}</span>
                    </li>
                  ))}
                </ol>
              )}
              <button type="button" onClick={onRemove} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-rose-500">
                <Trash2 size={12} /> Remove from deals
              </button>
            </div>
          )}
        </section>
      </div>
    </SheetContent>
  );
}
