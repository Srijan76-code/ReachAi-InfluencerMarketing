"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ChevronDown, Loader2, MoreHorizontal, Send } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field, Input, NumberInput } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { Select } from "@/components/ui/select";
import { ProposalCard } from "@/components/deals/NeedsYou";
import { btn, btnPrimary, textarea } from "@/lib/ui";
import { type Deal, type DealEvent, DEAL_TYPES, DELIVERABLES, type Proposal, USAGE, money } from "@/data/deals";
import { updatedLabel } from "@/types/campaign";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

const opts = <T extends string>(list: readonly (readonly [T, string])[]) => list.map(([value, l]) => ({ value, label: l }));
const label = <T extends string>(list: readonly (readonly [T, string])[], v: string) => list.find(([k]) => k === v)?.[1] ?? v;
export const askWords = (fee: number | null | undefined, pct: number | null | undefined) =>
  fee == null && pct ? `${pct}% commission` : `${money(fee ?? 0)}${pct ? ` + ${pct}%` : ""}`;

function errorText(e: unknown, fallback: string) {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

type Bubble = { who: "you" | "them"; text: string; at: string | null; note?: string };

/** The conversation, oldest first: what we sent and what they wrote (Gmail or pasted). */
function bubbles(events: DealEvent[]): Bubble[] {
  const out: Bubble[] = [];
  for (const e of [...events].reverse()) {
    const p = (e.payload || {}) as Record<string, unknown>;
    if (e.type === "message_sent" && p.text) {
      out.push({ who: "you", text: String(p.text), at: e.at, note: p.via === "gmail" ? "Sent from Gmail" : "Marked sent" });
    } else if (e.type === "creator_reply" && p.text) {
      const ask = p.their_ask as { fee?: number | null; commission_pct?: number } | undefined;
      out.push({ who: "them", text: String(p.text), at: e.at,
                 note: [p.source === "gmail" ? "From Gmail" : "Pasted", ask ? `asked ${askWords(ask.fee, ask.commission_pct)}` : null].filter(Boolean).join(" · ") });
    }
  }
  return out;
}

/** One negotiation as a chat (spec §8.6b): the messages, the agent's suggested reply, and a box to write or paste. */
export function DealChat({ deal, api, proposals, gmailReady, onChange, onProposals, onRemove, onBack }: {
  deal: Deal;
  api: Api;
  proposals: Proposal[];
  gmailReady: boolean;
  onChange: (d: Deal) => void;
  onProposals: (data: { proposals?: Proposal[] }) => void;
  onRemove: () => void;
  onBack?: () => void; // phones: back to the list
}) {
  const [events, setEvents] = useState<DealEvent[]>([]);
  const [mode, setMode] = useState<"write" | "paste">("write");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<"send" | "read" | "again" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [termsOpen, setTermsOpen] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  const loadEvents = () =>
    api(`/api/deals/${deal.id}/events`).then((r) => Array.isArray(r.data) && setEvents(r.data as DealEvent[])).catch(() => {});
  useEffect(() => {
    loadEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [deal.id, deal.updated_at, proposals.length]);
  useEffect(() => {
    void end.current?.scrollIntoView({ block: "end" }); // newer browsers return a promise here; the effect must not
  }, [events.length, proposals.length]);

  const save = async (patch: Record<string, unknown>) => {
    setError(null);
    try {
      onChange((await api(`/api/deals/${deal.id}`, { method: "PATCH", data: patch })).data as Deal);
    } catch (e) {
      setError(errorText(e, "Couldn't save that. Try again."));
    }
  };

  const run = async (kind: "send" | "read" | "again") => {
    setBusy(kind);
    setError(null);
    try {
      const url = kind === "send" ? `/api/deals/${deal.id}/message` : kind === "read" ? `/api/deals/${deal.id}/reply` : `/api/deals/${deal.id}/negotiate`;
      if (kind === "send" && !gmailReady) {
        try {
          await navigator.clipboard.writeText(text);
        } catch {} // copying can be blocked; it's still recorded
      }
      const r = (await api(url, { method: "POST", data: kind === "again" ? undefined : { text } })).data as { deal: Deal; proposals: Proposal[] };
      if (kind !== "again") setText("");
      onChange(r.deal);
      onProposals(r);
    } catch (e) {
      setError(errorText(e, "That didn't work. Try again."));
    } finally {
      setBusy(null);
    }
  };

  const a = deal.advice;
  const chat = bubbles(events);
  const lastReply = events.find((e) => e.type === "creator_reply");
  const lastAgent = (lastReply?.payload as { agent?: { action: string; reasons: string[] } } | undefined)?.agent;
  const stuck = !proposals.length && lastAgent && !["counter", "agree", "lost"].includes(lastAgent.action) && chat[chat.length - 1]?.who === "them";
  const lastOffer = [...events].find((e) => e.type === "message_sent" && (e.payload as { terms?: unknown })?.terms);
  const offer = (lastOffer?.payload as { terms?: { fee?: number | null; commission_pct?: number } } | undefined)?.terms;
  const facts = [
    a.fair_high != null ? `Fair ${money(a.fair_low)}–${money(a.fair_high)}` : "No fair price yet",
    deal.quoted_rate != null ? `They ask ${askWords(deal.quoted_rate, deal.quoted_commission_pct)}` : null,
    offer ? `You offered ${askWords(offer.fee, offer.commission_pct)}` : null,
    deal.agreed_rate != null && deal.stage !== "contacted" && deal.stage !== "negotiating" ? `Agreed ${askWords(deal.agreed_rate, deal.deal_type !== "flat" ? deal.commission_pct : null)}` : null,
  ].filter(Boolean).join(" · ");
  const commission = deal.deal_type === "base_plus_commission" || deal.deal_type === "affiliate";
  const talking = deal.stage === "contacted" || deal.stage === "negotiating";

  return (
    <div className="flex flex-col h-full min-h-0 min-w-0">
      {/* header */}
      <div className="px-4 py-3 border-b border-zinc-200/70 dark:border-zinc-800/70 flex items-center gap-3">
        {onBack && (
          <button type="button" onClick={onBack} aria-label="Back to the list" className="md:hidden text-zinc-500"><ArrowLeft size={16} /></button>
        )}
        <CreatorAvatar name={deal.name} src={deal.avatar_url} className="w-8 h-8 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center shrink-0" textClassName="text-xs font-medium" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate">
            {deal.url ? <a href={deal.url} target="_blank" rel="noopener noreferrer" className="hover:underline underline-offset-4">{deal.name}</a> : deal.name}
          </p>
          <p className="text-[11px] text-zinc-500 truncate">{facts}</p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" aria-label="More" className="h-[30px] w-[30px] shrink-0 flex items-center justify-center rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800"><MoreHorizontal size={16} /></button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
            <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => setTermsOpen((v) => !v)}>{termsOpen ? "Hide terms" : "Terms and email"}</DropdownMenuItem>
            {talking && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => save({ stage: "agreed", agreed_rate: deal.agreed_rate ?? deal.quoted_rate })}>Mark agreed</DropdownMenuItem>}
            {deal.stage !== "lost" ? (
              <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => save({ stage: "lost" })}>Mark lost</DropdownMenuItem>
            ) : (
              <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => save({ stage: "negotiating" })}>Reopen</DropdownMenuItem>
            )}
            <DropdownMenuItem className="text-xs cursor-pointer text-rose-500 focus:text-rose-500" onSelect={onRemove}>Remove from deals</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* terms, folded away */}
      {termsOpen && (
        <div className="px-4 py-3 border-b border-zinc-200/70 dark:border-zinc-800/70 space-y-3 bg-zinc-50/60 dark:bg-[#0a0b0c]">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Their email"><Input value={deal.contact_email ?? null} onSave={(v) => save({ contact_email: v })} placeholder="their@email.com" /></Field>
            <Field label="Deliverable"><Select label="Deliverable" value={deal.deliverable} onChange={(v) => save({ deliverable: v })} options={opts(DELIVERABLES)} /></Field>
            <Field label="Deal type"><Select label="Deal type" value={deal.deal_type} onChange={(v) => save({ deal_type: v })} options={opts(DEAL_TYPES)} /></Field>
            {commission && <Field label="Commission (%)"><NumberInput value={deal.commission_pct} onSave={(v) => save({ commission_pct: v })} placeholder="10" /></Field>}
            <Field label="Usage rights"><Select label="Usage rights" value={deal.usage_rights} onChange={(v) => save({ usage_rights: v })} options={opts(USAGE)} /></Field>
            <Field label="Fair price from"><NumberInput prefix="$" value={a.fair_low} onSave={(v) => save({ fair_low: v })} placeholder="Low" /></Field>
            <Field label="To"><NumberInput prefix="$" value={a.fair_high} onSave={(v) => save({ fair_high: v })} placeholder="High" /></Field>
          </div>
          <button type="button" onClick={() => setTermsOpen(false)} className="text-[11px] text-zinc-500 flex items-center gap-1">Done <ChevronDown size={11} className="rotate-180" /></button>
        </div>
      )}
      {!termsOpen && (
        <button type="button" onClick={() => setTermsOpen(true)} className="px-4 py-1.5 text-left text-[11px] text-zinc-500 border-b border-zinc-200/70 dark:border-zinc-800/70 truncate hover:text-zinc-800 dark:hover:text-zinc-200">
          {[label(DELIVERABLES, deal.deliverable), label(DEAL_TYPES, deal.deal_type), label(USAGE, deal.usage_rights), deal.contact_email ?? "No email yet"].join(" · ")}
        </button>
      )}

      {/* messages */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3">
        {chat.length === 0 && (
          <p className="text-xs text-zinc-500 text-center py-8">
            No messages yet. Send your pitch from Outreach, or write to them below.
          </p>
        )}
        {chat.map((b, i) => (
          <div key={i} className={`flex ${b.who === "you" ? "justify-end" : "justify-start"}`}>
            <div className="max-w-[82%] min-w-0 space-y-1">
              <div className={`rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap break-words ${b.who === "you"
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 rounded-br-md"
                : "bg-zinc-100 text-zinc-800 dark:bg-[#17181a] dark:text-zinc-200 rounded-bl-md"}`}>
                {b.text}
              </div>
              <p className={`text-[10px] text-zinc-500 ${b.who === "you" ? "text-right" : ""}`}>{[b.note, b.at ? updatedLabel(b.at) : null].filter(Boolean).join(" · ")}</p>
            </div>
          </div>
        ))}

        {/* the agent's suggested reply, as a draft */}
        {proposals.map((p) => (
          <div key={`${p.id}:${p.message}`} className="flex justify-end">
            <div className="w-full max-w-[90%]">
              <p className="text-[11px] text-zinc-500 mb-1 text-right">ReachAI suggests</p>
              <ProposalCard p={p} api={api} onDone={onProposals} />
            </div>
          </div>
        ))}

        {stuck && (
          <div className="rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 p-3 space-y-2.5">
            <p className="text-xs text-zinc-600 dark:text-zinc-400">{lastAgent!.reasons.join(" ")}</p>
            {a.fair_high == null && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Fair price from"><NumberInput prefix="$" value={a.fair_low} onSave={(v) => save({ fair_low: v })} placeholder="Low" /></Field>
                <Field label="To"><NumberInput prefix="$" value={a.fair_high} onSave={(v) => save({ fair_high: v })} placeholder="High" /></Field>
              </div>
            )}
            <button type="button" onClick={() => run("again")} disabled={!!busy || a.fair_high == null} className={btn}>
              {busy === "again" && <Loader2 size={13} className="animate-spin" />} {busy === "again" ? "Reading and deciding" : "Suggest a reply"}
            </button>
          </div>
        )}
        {busy === "read" && <p className="text-[11px] text-zinc-500 flex items-center gap-1.5"><Loader2 size={12} className="animate-spin" /> Reading their reply and deciding what to send…</p>}
        <div ref={end} />
      </div>

      {/* write or paste */}
      {deal.stage !== "lost" && (
        <div className="border-t border-zinc-200/70 dark:border-zinc-800/70 p-3 space-y-2">
          {error && <p className="text-[11px] text-rose-500">{error}</p>}
          <div className="flex items-center justify-between gap-2">
            <Segmented label="Message box" size="sm" value={mode} onChange={setMode}
              options={[{ value: "write", label: "Write to them" }, { value: "paste", label: "Paste their reply" }]} />
            <span className="text-[11px] text-zinc-500 truncate">
              {mode === "write" ? (gmailReady && deal.contact_email ? "Sends from your Gmail" : "Copied for you to send") : "We'll read it and suggest a reply"}
            </span>
          </div>
          <div className="flex items-end gap-2">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, 5000))}
              onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && text.trim() && !busy && run(mode === "write" ? "send" : "read")}
              rows={2}
              aria-label={mode === "write" ? "Your message" : "Their reply"}
              placeholder={mode === "write" ? "Write a message…" : "Paste what they said, or type their ask, like $20 + 10% commission"}
              className={`${textarea} flex-1`}
            />
            <button type="button" onClick={() => run(mode === "write" ? "send" : "read")} disabled={!!busy || !text.trim()} className={`${btnPrimary} h-[38px]`}>
              {busy === "send" || busy === "read" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
              {mode === "write" ? (gmailReady && deal.contact_email ? "Send" : "Copy") : "Read"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
