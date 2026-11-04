"use client";

import { useEffect, useState } from "react";
import { CircleDollarSign, ExternalLink, Handshake, History, ListChecks, NotebookPen, Trash2 } from "lucide-react";
import { SheetContent, SheetTitle } from "@/components/ui/sheet";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Field, Input, NumberInput, TextArea } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { SectionHeader, StatStrip, StatTile } from "@/components/ui/stat";
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

const VERDICT: Record<string, { label: string; tone: "good" | "warn" | "bad" }> = {
  great: { label: "Good price", tone: "good" },
  accept: { label: "Fair, accept", tone: "good" },
  counter: { label: "Counter", tone: "warn" },
  walk_away: { label: "Too high", tone: "bad" },
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
    case "creator_reply":
      return "Their reply pasted";
    case "message_sent":
      return `Message sent${p.edited ? " (you edited it)" : ""}`;
    case "proposal":
      return `${p.decision === "skipped" ? "Skipped" : "Approved"}: ${p.title}`;
    default:
      return e.type;
  }
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
  const [read, setRead] = useState<string[] | null>(null);

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
      onChange(r.data as Deal);
      loadEvents();
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Couldn't save that. Try again.");
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
      setRead(
        s.ignored
          ? ["it looked aimed at an AI, so we ignored it"]
          : [
              (s.declined as number) >= F ? "they're turning it down" : null,
              (s.agrees as number) >= F ? "they accept your offer" : null,
              (s.gives_price as number) >= F ? "they give a price" : null,
              (s.open_to_negotiate as number) >= F ? "open to negotiating" : null,
              (s.firm_price as number) >= F ? "the price is firm" : null,
              (s.wants_commission as number) >= F ? "open to commission" : null,
              (s.mentions_usage as number) >= F ? "mentions usage or exclusivity" : null,
            ].filter((x): x is string => !!x),
      );
      setReply("");
      onProposals(r);
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Couldn't read their reply. Try again.");
    } finally {
      setReading(false);
    }
  };

  const a = deal.advice;
  const verdict = a.verdict ? VERDICT[a.verdict] : null;
  const talking = ["contacted", "negotiating"].includes(deal.stage);
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

        {/* next step: the agent's suggestions for this deal, and pasting their reply */}
        <section className="space-y-3">
          <SectionHeader icon={<ListChecks size={14} className="text-zinc-400" />}>Next step</SectionHeader>
          {proposals.map((p) => <ProposalCard key={`${p.id}:${p.message}`} p={p} api={api} onDone={onProposals} />)}
          {proposals.length === 0 && (
            <p className="text-xs text-zinc-500 leading-relaxed">
              {talking
                ? "Nothing to do yet. When they answer, paste their reply below and we'll suggest what to send back."
                : "Nothing needs you on this deal right now."}
            </p>
          )}
          {talking && (
            <div className="space-y-2">
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value.slice(0, 3000))}
                rows={3}
                aria-label="Their reply"
                placeholder="Paste their reply here"
                className={textarea}
              />
              <div className="flex items-center gap-3">
                <button type="button" onClick={readReply} disabled={reading || !reply.trim()} className={btn}>
                  {reading ? "Reading…" : "Read their reply"}
                </button>
                {read && <span className="text-[11px] text-zinc-500 truncate">{read.length ? `Read: ${read.join(", ")}` : "Read: nothing that changes the next step"}</span>}
              </div>
            </div>
          )}
          <p className="text-[11px] text-zinc-500 leading-relaxed">
            Prices are worked out in code. Jev reads their reply; AI only rewords messages when you ask, and we check the numbers didn&apos;t change. Nothing is sent or changed until you approve it.
          </p>
        </section>

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
