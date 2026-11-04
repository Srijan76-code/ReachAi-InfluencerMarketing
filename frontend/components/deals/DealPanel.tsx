"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ExternalLink, Loader2, Trash2 } from "lucide-react";
import { SheetContent, SheetTitle } from "@/components/ui/sheet";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Field, Input, NumberInput, TextArea } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { SectionHeader } from "@/components/ui/stat";
import { btn, btnPrimary, textarea } from "@/lib/ui";
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

const words = (fee: number | null | undefined, pct: number | null | undefined) =>
  fee == null && pct ? `${pct}% commission only` : `${money(fee ?? 0)}${pct ? ` + ${pct}% commission` : ""}`;

/** The negotiation so far, oldest first: what they asked for (as the agent read it) and what we offered. */
function negotiation(events: DealEvent[]): { who: "them" | "you"; text: string }[] {
  const out: { who: "them" | "you"; text: string }[] = [];
  for (const e of [...events].reverse()) {
    const p = (e.payload || {}) as Record<string, unknown>;
    const ask = p.their_ask as { fee?: number | null; commission_pct?: number } | undefined;
    if (e.type === "creator_reply" && ask) out.push({ who: "them", text: `Asked ${words(ask.fee, ask.commission_pct)}` });
    if (e.type === "message_sent" && (p.terms || p.amounts)) {
      const t = (p.terms ?? {}) as { fee?: number | null; commission_pct?: number };
      const a = (p.amounts ?? {}) as Record<string, number>;
      const offer = p.terms ? words(t.fee, t.commission_pct) : a.base ? words(a.base, a.commission_pct) : money(a.price ?? a.counter);
      out.push({ who: "you", text: `${p.kind === "agree" ? "Agreed to" : "Offered"} ${offer}${p.final ? " (final)" : ""}` });
    }
  }
  return out;
}

export function DealPanel({ deal, api, onChange, onRemove, proposals, onProposals, gmailReady = false }: {
  deal: Deal;
  api: Api;
  onChange: (d: Deal) => void;
  onRemove: () => void;
  proposals: Proposal[];
  onProposals: (data: { proposals?: Proposal[] }) => void;
  gmailReady?: boolean;
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
    setRead(null);
    try {
      const r = (await api(`/api/deals/${deal.id}/reply`, { method: "POST", data: { text: reply } })).data as {
        agent: { action: string; reasons: string[] };
        deal: Deal;
        proposals: Proposal[];
      };
      if (!["counter", "agree", "lost"].includes(r.agent?.action)) setRead((r.agent?.reasons ?? []).join(" ") || "Nothing in it changes the next step.");
      setReply("");
      onChange(r.deal);
      onProposals(r);
    } catch (e) {
      setError(errorText(e, "Couldn't read that. Try again."));
    } finally {
      setReading(false);
    }
  };

  const a = deal.advice;
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

          {(talking || posting) && (
            <Field label="Their email" hint={gmailReady
              ? (deal.emailing ? "You're emailing them from your Gmail. Their replies come in here by themselves." : "Messages you approve are sent here from your Gmail.")
              : "Connect Gmail (top of the page) to send from your own address."}>
              <Input value={deal.contact_email ?? null} onSave={(v) => save({ contact_email: v })} placeholder="their@email.com" />
            </Field>
          )}

          {talking && (
            <div className="space-y-2 pt-1">
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value.slice(0, 3000))}
                onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && reply.trim() && !reading && readReply()}
                rows={3}
                aria-label="What they said"
                placeholder={deal.emailing && gmailReady
                  ? "Replied somewhere else (DM, WhatsApp)? Paste it, or type what they asked for, like $7 + 20% commission"
                  : "Paste their reply, or type what they asked for, like $7 + 20% commission"}
                className={textarea}
              />
              <div className="flex items-center gap-3 min-w-0">
                <button type="button" onClick={readReply} disabled={reading || !reply.trim()} className={btnPrimary}>
                  {reading && <Loader2 size={13} className="animate-spin" />} {reading ? "Reading and deciding" : "Suggest a reply"}
                </button>
                {reading && <span className="text-[11px] text-zinc-500">Takes a few seconds</span>}
              </div>
              {read && <p className="text-[11px] text-zinc-500 leading-relaxed">{read}</p>}
            </div>
          )}
        </section>

        {/* where the price stands, while you're talking price */}
        {talking && (history.length > 0 || a.fair_high != null) && (
          <section className="space-y-3">
            <SectionHeader>Price</SectionHeader>
            {a.fair_high != null && (
              <p className="text-xs text-zinc-500 leading-relaxed">
                Fair for this deal: <span className="font-mono text-zinc-900 dark:text-zinc-100">{money(a.fair_low)}–{money(a.fair_high)}</span>
                {deal.quoted_rate != null && (
                  <>. They asked <span className="font-mono text-zinc-900 dark:text-zinc-100">{words(deal.quoted_rate, deal.quoted_commission_pct)}</span></>
                )}.
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
