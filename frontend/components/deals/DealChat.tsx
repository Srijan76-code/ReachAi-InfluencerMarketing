"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  AlertCircle, ArrowLeft, ArrowUp, Check, ChevronDown, Clipboard, Clock, Handshake, Info, Instagram, Loader2, Mail, MessageCircle,
  MoreHorizontal, RotateCcw, Sparkles, Twitter, X,
} from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Burst } from "@/components/chat/burst";
import { Conversation, ConversationContent, ConversationScrollButton } from "@/components/chat/conversation";
import { Shimmer, TypingDots } from "@/components/chat/shimmer";
import { AgreeSheet } from "@/components/deals/AgreeSheet";
import { DealDetails } from "@/components/deals/DealDetails";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field, NumberInput } from "@/components/ui/field";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { inboxStore } from "@/lib/inbox";
import { btn } from "@/lib/ui";
import { type Channel, CHANNELS, type Deal, type DealEvent, type Proposal, money } from "@/data/deals";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
type Who = "you" | "them";
type Op = { kind: "draft"; proposalId: string } | { kind: "own" } | { kind: "paste" };
type Pending = { key: string; who: Who; text: string; status: "sending" | "failed"; op: Op; error?: Problem };
type Problem = { text: string; action?: "reconnect" | "retry" };
type Bubble = { key: string; who: Who; text: string; at: string | null; source?: "gmail" | "pasted" | "copied"; pending?: Pending };

export const askWords = (fee: number | null | undefined, pct: number | null | undefined) =>
  fee == null && pct ? `${pct}% commission` : `${money(fee ?? 0)}${pct ? ` + ${pct}%` : ""}`;

const firstName = (name: string) => (name.split(/[\s|·-]+/)[0] || name).slice(0, 18);
const timeOf = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "");
function dayOf(iso: string | null) {
  if (!iso) return "Today";
  const d = new Date(iso);
  const today = new Date();
  const y = new Date(today);
  y.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === y.toDateString()) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

/** A short, plain reason and what to do about it (2-4 words + one action). */
function problem(e: unknown, fallback: string): Problem {
  const r = (e as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
  const detail = typeof r?.data?.detail === "string" ? r.data.detail : "";
  if (!r) return { text: "Can't reach ReachAI", action: "retry" };
  if (r.status === 409 && /gmail/i.test(detail)) return { text: "Gmail disconnected", action: "reconnect" };
  if (r.status === 429) return { text: "Daily email limit reached. Try tomorrow" };
  if (r.status === 409 && /already/i.test(detail)) return { text: detail.replace(/\.$/, "") };
  if (r.status && r.status >= 500) return { text: "Couldn't send", action: "retry" };
  return { text: (detail || fallback).replace(/\.$/, "") };
}

function bubblesFrom(events: DealEvent[]): Bubble[] {
  const out: Bubble[] = [];
  [...events].reverse().forEach((e, i) => {
    const p = (e.payload || {}) as Record<string, unknown>;
    const key = `${e.type}:${e.at}:${i}`;
    if (e.type === "message_sent" && p.text) out.push({ key, who: "you", text: String(p.text), at: e.at, source: p.via === "gmail" ? "gmail" : "copied" });
    else if (e.type === "creator_reply" && p.text) out.push({ key, who: "them", text: String(p.text), at: e.at, source: p.source === "gmail" ? "gmail" : "pasted" });
  });
  return out;
}

const CHANNEL_ICON: Record<Channel, typeof Mail> = { email: Mail, instagram: Instagram, twitter: Twitter, whatsapp: MessageCircle, other: Clipboard };
const PROFILE: Partial<Record<Channel, (d: Deal) => string | undefined>> = {
  instagram: (d) => d.socials?.instagram,
  twitter: (d) => d.socials?.twitter,
  whatsapp: () => "https://web.whatsapp.com/",
};

const SOURCE: Record<string, { icon: typeof Mail; label: string }> = {
  gmail: { icon: Mail, label: "Email" },
  pasted: { icon: Clipboard, label: "Pasted" },
  copied: { icon: Clipboard, label: "Copied to send yourself" },
};

/** One message, with its time on hover and (for yours) whether it went out. */
function MessageBubble({ b, first, last, isNew, name, onRetry, onReconnect }: {
  b: Bubble; first: boolean; last: boolean; isNew: boolean; name: string; onRetry: () => void; onReconnect: () => void;
}) {
  const reduce = useReducedMotion();
  const mine = b.who === "you";
  const src = b.source ? SOURCE[b.source] : null;
  const failed = b.pending?.status === "failed";
  return (
    <motion.div
      layout={!reduce}
      initial={isNew && !reduce ? { opacity: 0, y: 18, scale: 0.94 } : false}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 420, damping: 28, mass: 0.8 }}
      className={`group flex flex-col ${mine ? "items-end" : "items-start"} ${first ? "mt-4" : "mt-1"}`}
    >
      {first && <p className="text-[11px] font-medium text-zinc-500 mb-1 px-1">{mine ? "You" : name}</p>}
      <div className={`flex items-end gap-2 max-w-[78%] min-w-0 ${mine ? "flex-row-reverse" : ""}`}>
        <div
          className={`min-w-0 px-3.5 py-2 text-[13.5px] leading-relaxed whitespace-pre-wrap break-words text-zinc-800 dark:text-zinc-100 rounded-[18px]
            ${mine ? "bg-zinc-200/80 dark:bg-[#26272b]" : "bg-zinc-100 dark:bg-[#17181a]"}
            ${mine ? (last ? "rounded-br-md" : "") : last ? "rounded-bl-md" : ""}
            ${b.pending?.status === "sending" ? "opacity-70" : ""} ${failed ? "ring-1 ring-rose-500/50" : ""}`}
        >
          {b.text}
        </div>
        <span className="shrink-0 pb-1 text-[10px] text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 whitespace-nowrap">
          {src && <src.icon size={10} aria-label={src.label} />} {timeOf(b.at)}
        </span>
      </div>
      {b.source === "pasted" && !b.pending && last && <p className="text-[10px] text-zinc-400 mt-1 px-1">Pasted</p>}
      {b.pending?.status === "sending" && (
        <p className="text-[10px] text-zinc-400 mt-1 px-1 flex items-center gap-1"><Clock size={10} /> {mine ? "Sending…" : "Adding…"}</p>
      )}
      {failed && (
        <p className="text-[11px] text-rose-500 mt-1 px-1 flex items-center gap-1.5">
          <AlertCircle size={11} /> {b.pending?.error?.text ?? "Not sent"}
          {b.pending?.error?.action === "reconnect" ? (
            <button type="button" onClick={onReconnect} className="underline underline-offset-2">Reconnect</button>
          ) : (
            <button type="button" onClick={onRetry} className="underline underline-offset-2 flex items-center gap-0.5"><RotateCcw size={10} /> Retry</button>
          )}
        </p>
      )}
    </motion.div>
  );
}

/** How you reach them: email (sent from Gmail) or a DM (copied, then their profile opens). */
function ChannelChip({ channel, deal, gmailReady, onPick }: { channel: Channel; deal: Deal; gmailReady: boolean; onPick: (c: Channel) => void }) {
  const Icon = CHANNEL_ICON[channel];
  const label = CHANNELS.find((c) => c.value === channel)?.label ?? "Email";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" aria-label={`Reach them by ${label}. Change`}
          className="h-8 px-2.5 rounded-full border border-zinc-200 dark:border-zinc-800 text-[11px] text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center gap-1.5 transition-colors">
          <Icon size={12} /> <span className="hidden sm:inline">{label}</span> <ChevronDown size={11} className="text-zinc-400" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
        <DropdownMenuLabel className="text-[11px] font-normal text-zinc-500">How you reach {deal.name}</DropdownMenuLabel>
        {CHANNELS.map((c) => {
          const I = CHANNEL_ICON[c.value];
          const hint = c.value === "email" ? (deal.contact_email ? (gmailReady ? "Sends from your Gmail" : "Connect Gmail to send") : "Add their email in Details")
            : c.value === "other" ? "Copy and paste it yourself" : PROFILE[c.value]?.(deal) ? "Copies it and opens their profile" : "Copies it";
          return (
            <DropdownMenuItem key={c.value} className="text-xs cursor-pointer flex items-start gap-2" onSelect={() => onPick(c.value)}>
              <I size={13} className="mt-0.5 shrink-0" />
              <span className="flex-1">
                <span className="block">{c.label}</span>
                <span className="block text-[10px] text-zinc-500">{hint}</span>
              </span>
              {c.value === channel && <Check size={12} className="mt-0.5" />}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ChatSkeleton() {
  return (
    <div className="flex-1 px-5 md:px-8 py-8 space-y-4" aria-label="Loading the conversation">
      {[["l", "w-2/5"], ["l", "w-3/5"], ["r", "w-1/2"], ["l", "w-1/3"], ["r", "w-2/5"]].map(([side, w], i) => (
        <div key={i} className={`flex ${side === "r" ? "justify-end" : ""}`}>
          <div className={`${w} h-10 rounded-[18px] bg-zinc-100 dark:bg-[#141517] animate-pulse motion-reduce:animate-none`} />
        </div>
      ))}
    </div>
  );
}

/** One negotiation as a chat (spec §8.6b): the messages, ReachAI's draft in the message box, and a switch to
 * add what the creator said when it came by DM. */
export function DealChat({ deal, api, proposals, gmailReady, website, onReconnect, onChange, onProposals, onRemove, onBack, onRead }: {
  deal: Deal;
  website: string | null; // the founder's site, for tracking links
  api: Api;
  proposals: Proposal[];
  gmailReady: boolean;
  onReconnect: () => void;
  onChange: (d: Deal) => void;
  onProposals: (data: { proposals?: Proposal[] }) => void;
  onRemove: () => void;
  onBack?: () => void; // phones: back to the list
  onRead: () => void;
}) {
  const [events, setEvents] = useState<DealEvent[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [pending, setPending] = useState<Pending[]>([]);
  const [drafting, setDrafting] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [celebrate, setCelebrate] = useState(false);
  const [who, setWho] = useState<Who>("you");
  const [texts, setTexts] = useState<Record<Who, string>>({ you: "", them: "" });
  const [busy, setBusy] = useState<"reword" | "discard" | "accept" | "again" | null>(null);
  const [note, setNote] = useState<Problem | null>(null);
  const [agreeOpen, setAgreeOpen] = useState(false);
  const [subject, setSubject] = useState("");
  const initialKeys = useRef<Set<string> | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const name = firstName(deal.name);

  const draft = proposals.find((p) => p.is_message) ?? null;
  // ReachAI's draft fills the message box; a new draft replaces what's there (your own unsent text stays if there's no draft)
  const [draftFor, setDraftFor] = useState<string | null>(null);
  if ((draft?.id ?? null) !== draftFor) {
    setDraftFor(draft?.id ?? null);
    if (draft?.message) {
      setTexts((t) => ({ ...t, you: draft.message ?? "" }));
      setSubject(draft.subject ?? "");
      setWho("you");
    }
  }
  const channel: Channel = deal.channel ?? (deal.contact_email ? "email" : "other");
  const firstEmail = channel === "email" && !deal.emailing && !(deal.last_message);

  // a first message you've looked at can go out with "Send all reviewed"
  useEffect(() => {
    if (draft?.kind === "pitch" && !draft.seen) api(`/api/proposals/${draft.id}/seen`, { method: "POST" }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per draft
  }, [draft?.id]);

  const loadEvents = () =>
    api(`/api/deals/${deal.id}/events`)
      .then((r) => {
        if (Array.isArray(r.data)) {
          setEvents(r.data as DealEvent[]);
          setLoadFailed(false);
        }
      })
      .catch(() => setLoadFailed(true));
  useEffect(() => {
    loadEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [deal.id, deal.updated_at, deal.last_message?.at, proposals.length]);

  // opening the chat reads it
  useEffect(() => {
    if (!deal.unread) return;
    api(`/api/deals/${deal.id}/read`, { method: "POST" }).catch(() => {});
    inboxStore.markRead(deal.id);
    onRead();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per new reply
  }, [deal.id, deal.unread]);

  // grow the message box with its text (up to ~8 lines)
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    if (el.scrollHeight) el.style.height = `${Math.min(el.scrollHeight, 200)}px`; // 0 while hidden (phones): keep auto
  }, [texts, who, deal.id]);

  const bubbles = useMemo(() => {
    const saved = events ? bubblesFrom(events) : [];
    if (events && initialKeys.current === null) initialKeys.current = new Set(saved.map((b) => b.key));
    return [...saved, ...pending.map((p) => ({ key: p.key, who: p.who, text: p.text, at: new Date().toISOString(), pending: p }) as Bubble)];
  }, [events, pending]);

  const canSend = channel === "email" && gmailReady && !!deal.contact_email;
  const talking = deal.stage === "contacted" || deal.stage === "negotiating";
  const agreed = !talking && deal.stage !== "lost";

  const lastReply = events?.find((e) => e.type === "creator_reply");
  const lastAgent = (lastReply?.payload as { agent?: { action: string; reasons: string[] } } | undefined)?.agent;
  const stuck = !!events && !draft && !drafting && !!lastAgent && lastAgent.action === "none" && bubbles[bubbles.length - 1]?.who === "them";

  const run = async (op: Op, text: string, retryKey?: string) => {
    const key = retryKey ?? `p${Date.now()}`;
    const mine = op.kind !== "paste";
    const stageBefore = deal.stage;
    setNote(null);
    setPending((ps) => (retryKey ? ps.map((p) => (p.key === key ? { ...p, status: "sending", error: undefined } : p))
      : [...ps, { key, who: mine ? "you" : "them", text, status: "sending", op }]));
    if (!retryKey) setTexts((t) => ({ ...t, [mine ? "you" : "them"]: "" }));
    if (op.kind === "paste") setDrafting(true);
    try {
      if (mine && !canSend) {
        try {
          await navigator.clipboard.writeText(text);
        } catch {} // copying can be blocked; it's still recorded
        const profile = PROFILE[channel]?.(deal);
        if (profile) window.open(profile, "_blank", "noopener,noreferrer");
      }
      const via = canSend ? "gmail" : "copy";
      const r = (await (op.kind === "draft" ? api(`/api/proposals/${op.proposalId}/approve`, { method: "POST", data: { message: text, via, subject: subject.trim() || null } })
        : op.kind === "own" ? api(`/api/deals/${deal.id}/message`, { method: "POST", data: { text, via } })
        : api(`/api/deals/${deal.id}/reply`, { method: "POST", data: { text } }))).data as { deal: Deal; proposals?: Proposal[] };
      await loadEvents();
      setPending((ps) => ps.filter((p) => p.key !== key));
      if (op.kind === "draft" && r.deal.stage === "agreed" && stageBefore !== "agreed") {
        setCelebrate(true);
        setTimeout(() => setCelebrate(false), 1200);
        setTimeout(() => setAgreeOpen(true), 700); // next: what they'll post, when, and their link and code
      }
      onChange(r.deal);
      onProposals(r);
      inboxStore.refresh();
      if (mine && !canSend) setNote({ text: channel === "email" || channel === "other" ? "Copied. Paste it where you talk to them" : `Copied. Paste it in ${CHANNELS.find((c) => c.value === channel)?.label}` });
    } catch (e) {
      setPending((ps) => ps.map((p) => (p.key === key ? { ...p, status: "failed", error: problem(e, mine ? "Not sent" : "Couldn't add it") } : p)));
    } finally {
      if (op.kind === "paste") setDrafting(false);
    }
  };

  const send = () => {
    const text = texts[who].trim();
    if (!text || pending.some((p) => p.status === "sending")) return;
    if (who === "them") return run({ kind: "paste" }, text);
    return run(draft ? { kind: "draft", proposalId: draft.id } : { kind: "own" }, text);
  };

  const call = async (kind: "reword" | "discard" | "accept" | "again") => {
    if (kind !== "again" && !draft) return;
    setBusy(kind);
    setNote(null);
    if (kind === "again") setDrafting(true);
    try {
      if (kind === "reword") {
        const r = (await api(`/api/proposals/${draft!.id}/reword`, { method: "POST" })).data as { message: string; source: string };
        if (r.source === "ai") setTexts((t) => ({ ...t, you: r.message }));
        else setNote({ text: "The new wording changed a number, so we kept this one" });
      } else if (kind === "discard") {
        const r = (await api(`/api/proposals/${draft!.id}/skip`, { method: "POST" })).data as { proposals?: Proposal[] };
        setTexts((t) => ({ ...t, you: "" }));
        onProposals(r);
      } else if (kind === "accept") {
        const r = (await api(`/api/proposals/${draft!.id}/accept-change`, { method: "POST" })).data as { deal: Deal; proposals?: Proposal[] };
        setTexts((t) => ({ ...t, you: "" }));
        onChange(r.deal);
        onProposals(r);
      } else {
        const r = (await api(`/api/deals/${deal.id}/negotiate`, { method: "POST" })).data as { deal: Deal; proposals?: Proposal[] };
        onChange(r.deal);
        onProposals(r);
      }
      inboxStore.refresh();
    } catch (e) {
      setNote(problem(e, "That didn't work"));
    } finally {
      setBusy(null);
      if (kind === "again") setDrafting(false);
    }
  };

  const save = async (patch: Record<string, unknown>) => {
    try {
      const d = (await api(`/api/deals/${deal.id}`, { method: "PATCH", data: patch })).data as Deal;
      if (patch.stage === "agreed") {
        setCelebrate(true);
        setTimeout(() => setCelebrate(false), 1200);
      }
      onChange(d);
    } catch (e) {
      setNote(problem(e, "Couldn't save that"));
    }
  };

  const a = deal.advice;
  const fair = a.fair_high != null ? `Fair ${money(a.fair_low)}–${money(a.fair_high)}` : "No fair price yet";
  const agreedWords = deal.agreed_rate != null ? askWords(deal.agreed_rate, deal.deal_type !== "flat" ? deal.commission_pct : null) : null;
  const change = draft?.kind === "hold_terms" ? draft.change : null;
  const sendLabel = who === "them" ? "Add" : draft?.kind === "agree" ? (canSend ? "Send and agree" : "Copy and agree") : canSend ? "Send"
    : CHANNELS.find((c) => c.value === channel)?.verb ?? "Copy";

  return (
    <div className="flex flex-col h-full min-h-0 min-w-0">
      {/* header: who, the fair price, how you reach them */}
      <div className="px-4 md:px-6 h-16 shrink-0 border-b border-zinc-200/70 dark:border-zinc-800/70 flex items-center gap-3">
        {onBack && (
          <button type="button" onClick={onBack} aria-label="Back to the list" className="md:hidden -ml-1 h-8 w-8 flex items-center justify-center text-zinc-500"><ArrowLeft size={16} /></button>
        )}
        <div className="relative shrink-0">
          <CreatorAvatar name={deal.name} src={deal.avatar_url} className="w-9 h-9 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center" textClassName="text-xs font-medium" />
          <Burst show={celebrate} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100 truncate">
            {deal.url ? <a href={deal.url} target="_blank" rel="noopener noreferrer" className="hover:underline underline-offset-4">{deal.name}</a> : deal.name}
          </p>
          <p className="text-[11px] text-zinc-500 truncate flex items-center gap-1.5">
            {agreed && agreedWords ? (
              <motion.span initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="text-emerald-600 dark:text-emerald-400 font-medium">Agreed {agreedWords}</motion.span>
            ) : deal.stage === "lost" ? <span>Not going ahead</span> : <span>{fair}</span>}
            {agreed && deal.posts && deal.posts.length > 0 && (
              <><span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span><span>{deal.posts.length} {deal.posts.length === 1 ? "post" : "posts"}</span></>
            )}
            {deal.link && <><span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span><span>{deal.link.clicks} {deal.link.clicks === 1 ? "click" : "clicks"}</span></>}
          </p>
        </div>
        <ChannelChip channel={channel} deal={deal} gmailReady={gmailReady} onPick={(c) => {
          save({ channel: c });
          if (draft?.kind === "pitch" && draft.texts) {
            const t = draft.texts[c] ?? draft.texts.instagram ?? draft.texts.twitter ?? draft.texts.email;
            if (t?.body) setTexts((x) => ({ ...x, you: t.body }));
          }
        }} />
        <button type="button" onClick={() => setDetailsOpen(true)} aria-label="Deal details" className="h-8 px-2.5 rounded-md text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center gap-1.5 transition-colors">
          <Info size={14} /> <span className="hidden sm:inline">Details</span>
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" aria-label="More" className="h-8 w-8 shrink-0 flex items-center justify-center rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800"><MoreHorizontal size={16} /></button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
            {talking && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => setAgreeOpen(true)}>Agree…</DropdownMenuItem>}
            {agreed && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => setAgreeOpen(true)}>Agreed terms</DropdownMenuItem>}
            {deal.stage !== "lost" ? (
              <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => save({ stage: "lost" })}>Mark lost</DropdownMenuItem>
            ) : (
              <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => save({ stage: "negotiating" })}>Reopen</DropdownMenuItem>
            )}
            <DropdownMenuItem className="text-xs cursor-pointer text-rose-500 focus:text-rose-500" onSelect={onRemove}>Remove</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* messages */}
      {events === null && !loadFailed ? (
        <ChatSkeleton />
      ) : loadFailed && events === null ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-xs text-zinc-500">
          Couldn&apos;t load messages
          <button type="button" onClick={loadEvents} className={btn}><RotateCcw size={12} /> Try again</button>
        </div>
      ) : (
        <Conversation>
          <ConversationContent>
            {bubbles.length === 0 && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="m-auto py-16 text-center">
                {deal.writing && !draft ? (
                  <>
                    <p className="text-[13px] flex items-center justify-center gap-2"><TypingDots /> <Shimmer>{`Writing a first message for ${name}`}</Shimmer></p>
                                      </>
                ) : draft?.kind === "pitch" ? (
                  <>
                    <p className="text-[13px] text-zinc-900 dark:text-zinc-100">Your first message to {name} is ready</p>
                                      </>
                ) : (
                  <>
                    <p className="text-[13px] text-zinc-900 dark:text-zinc-100">No messages yet</p>
                    <p className="text-xs text-zinc-500 mt-1">Write your first message to {name} below.</p>
                  </>
                )}
              </motion.div>
            )}
            {bubbles.map((b, i) => {
              const prev = bubbles[i - 1];
              const next = bubbles[i + 1];
              const newDay = !prev || dayOf(prev.at) !== dayOf(b.at);
              return (
                <div key={b.key} className="contents">
                  {newDay && (
                    <p className="self-center mt-6 mb-1 text-[10px] font-medium text-zinc-400 px-2 py-0.5 rounded-full bg-zinc-100/70 dark:bg-[#141517]">{dayOf(b.at)}</p>
                  )}
                  <MessageBubble b={b} name={name} first={!prev || prev.who !== b.who || newDay} last={!next || next.who !== b.who}
                    isNew={!initialKeys.current?.has(b.key)} onReconnect={onReconnect}
                    onRetry={() => b.pending && run(b.pending.op, b.pending.text, b.pending.key)} />
                </div>
              );
            })}
            <AnimatePresence>
              {drafting && (
                <motion.div key="drafting" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                  className="mt-4 self-end flex items-center gap-2 text-xs">
                  <TypingDots />
                  <Shimmer>ReachAI is reading and drafting a reply</Shimmer>
                </motion.div>
              )}
            </AnimatePresence>
            {stuck && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className="mt-6 self-center w-full max-w-md rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-3.5 space-y-2.5">
                <p className="text-xs text-zinc-600 dark:text-zinc-400 flex gap-1.5"><Sparkles size={13} className="text-violet-500 shrink-0 mt-0.5" /> {lastAgent!.reasons.join(" ")}</p>
                {a.fair_high == null && (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Fair price from"><NumberInput prefix="$" value={a.fair_low} onSave={(v) => save({ fair_low: v })} placeholder="Low" /></Field>
                    <Field label="To"><NumberInput prefix="$" value={a.fair_high} onSave={(v) => save({ fair_high: v })} placeholder="High" /></Field>
                  </div>
                )}
                <button type="button" onClick={() => call("again")} disabled={!!busy || a.fair_high == null} className={btn}>
                  <Sparkles size={12} className="text-violet-500" /> Suggest a reply
                </button>
              </motion.div>
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
      )}

      {/* agreed, but what they'll post isn't written down yet */}
      <AnimatePresence>
        {agreed && !change && !(deal.posts && deal.posts.length) && deal.posts !== undefined && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="shrink-0 px-4 md:px-6">
            <div className="mb-2 rounded-xl border border-emerald-300/60 dark:border-emerald-500/25 bg-emerald-50/50 dark:bg-emerald-500/5 px-3.5 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
              <p className="text-xs text-zinc-800 dark:text-zinc-200 flex-1 min-w-[200px]">
                <span className="font-medium">You agreed {agreedWords}.</span>
                              </p>
              <button type="button" onClick={() => setAgreeOpen(true)} className={btn}><Handshake size={12} /> Set up the deal</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* they asked for more after agreeing */}
      <AnimatePresence>
        {change && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="shrink-0 px-4 md:px-6">
            <div className="mb-2 rounded-xl border border-amber-300/60 dark:border-amber-500/30 bg-amber-50/60 dark:bg-amber-500/5 px-3.5 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
              <p className="text-xs text-zinc-800 dark:text-zinc-200 flex-1 min-w-[200px]">
                <span className="font-medium">Wants to change the deal:</span>{" "}
                <span className="font-mono">{askWords(change.from.fee, change.from.commission_pct)}</span> → <span className="font-mono">{askWords(change.to.fee, change.to.commission_pct)}</span>
                              </p>
              <button type="button" onClick={() => call("accept")} disabled={!!busy} className={btn}>
                {busy === "accept" && <Loader2 size={12} className="animate-spin" />} Accept {askWords(change.to.fee, change.to.commission_pct)}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* the message box */}
      {deal.stage !== "lost" && (
        <div className="shrink-0 px-4 md:px-6 pb-4 pt-1">
          <div className={`rounded-2xl border bg-white dark:bg-[#0f1011] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors
            ${who === "them" ? "border-blue-300/70 dark:border-blue-500/30" : "border-zinc-200 dark:border-zinc-800 focus-within:border-zinc-300 dark:focus-within:border-zinc-700"}`}>
            <div className="flex items-center gap-2 px-3 pt-2.5">
              {/* who's speaking: you, or them (paste what they said by DM) */}
              <div role="tablist" aria-label="Who is speaking" className="relative flex items-center p-0.5 rounded-full bg-zinc-100 dark:bg-[#17181a] text-[11px] font-medium">
                {(["you", "them"] as Who[]).map((w) => (
                  <button key={w} type="button" role="tab" aria-selected={who === w} onClick={() => setWho(w)}
                    className={`relative px-2.5 h-6 rounded-full transition-colors ${who === w ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"}`}>
                    {who === w && <motion.span layoutId={`who-${deal.id}`} className="absolute inset-0 rounded-full bg-white dark:bg-[#26272b] shadow-sm" transition={{ type: "spring", stiffness: 500, damping: 35 }} />}
                    <span className="relative">{w === "you" ? "You" : name}</span>
                    {w === "them" && texts.them && who !== "them" && <span className="relative ml-1 inline-block w-1 h-1 rounded-full bg-blue-500 align-middle" aria-label="Unsent text" />}
                  </button>
                ))}
              </div>
              <AnimatePresence mode="wait">
                {who === "you" && draft && (
                  <motion.span key={draft.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                    className="min-w-0 flex items-center gap-1 text-[11px] text-zinc-600 dark:text-zinc-300">
                    <Sparkles size={12} className="text-violet-500 shrink-0" />
                    <span className="truncate">{draft.title}</span>
                    {draft.reason && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button type="button" aria-label="Why this reply" className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 shrink-0"><Info size={12} /></button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs text-xs">{draft.reason}{draft.source === "ai" ? " Worded by AI, numbers checked." : ""}</TooltipContent>
                      </Tooltip>
                    )}
                  </motion.span>
                )}
                {who === "them" && (
                  <motion.span key="paste" initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="text-[11px] text-zinc-500 truncate">
                    Paste their reply
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
            {who === "you" && draft?.kind === "pitch" && firstEmail && (
              <input value={subject} onChange={(e) => setSubject(e.target.value.slice(0, 200))} placeholder="Subject" aria-label="Subject line"
                className="block w-full bg-transparent px-3.5 pt-2.5 pb-1 text-[13px] font-medium text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none border-b border-zinc-100 dark:border-zinc-800/70" />
            )}
            <textarea
              ref={box}
              value={texts[who]}
              onChange={(e) => setTexts((t) => ({ ...t, [who]: e.target.value.slice(0, 5000) }))}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  send();
                }
              }}
              rows={2}
              aria-label={who === "you" ? "Your message" : `What ${name} said`}
              placeholder={who === "you" ? `Write to ${name}…` : `Paste ${name}'s reply`}
              className="block w-full resize-none bg-transparent px-3.5 pt-2 pb-1 text-[13.5px] leading-relaxed text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none max-h-[200px]"
            />
            <div className="flex items-center gap-1.5 px-2.5 pb-2.5">
              <span className="text-[11px] text-zinc-400 truncate pl-1">
                {note ? (
                  <span className={`flex items-center gap-1 ${note.action ? "text-rose-500" : "text-zinc-500"}`}>
                    {note.text}
                    {note.action === "reconnect" && <button type="button" onClick={onReconnect} className="underline">Reconnect</button>}
                  </span>
                ) : who === "you" ? (canSend ? `From your Gmail to ${deal.contact_email}`
                  : channel === "email" ? (deal.contact_email ? "Connect Gmail to send" : "Add their email in Details")
                  : PROFILE[channel]?.(deal) ? "Copies and opens their profile" : "Copies the message")
                  : "⌘ Enter"}
              </span>
              <div className="ml-auto flex items-center gap-1">
                {who === "you" && draft?.can_reword && (
                  <button type="button" onClick={() => call("reword")} disabled={!!busy} className="h-8 px-2.5 rounded-full text-xs text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center gap-1.5 disabled:opacity-40">
                    {busy === "reword" ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} className="text-violet-500" />} Reword
                  </button>
                )}
                {who === "you" && draft && (
                  <button type="button" onClick={() => call("discard")} disabled={!!busy} aria-label="Discard the draft" title="Discard the draft"
                    className="h-8 w-8 rounded-full text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center justify-center disabled:opacity-40">
                    {busy === "discard" ? <Loader2 size={12} className="animate-spin" /> : <X size={14} />}
                  </button>
                )}
                <motion.button type="button" onClick={send} whileTap={{ scale: 0.92 }}
                  disabled={!texts[who].trim() || pending.some((p) => p.status === "sending")}
                  className={`h-8 rounded-full flex items-center justify-center gap-1.5 text-xs font-medium transition-opacity disabled:opacity-30
                    ${sendLabel.length > 4 ? "px-3" : "w-8"} ${who === "them" ? "bg-blue-500 text-white" : "bg-zinc-900 text-white dark:bg-zinc-300 dark:text-zinc-900"}`}
                  aria-label={sendLabel}>
                  {sendLabel.length > 4 ? <>{draft?.kind === "agree" ? <Check size={13} /> : <ArrowUp size={14} />} {sendLabel}</> : <ArrowUp size={15} />}
                </motion.button>
              </div>
            </div>
          </div>
        </div>
      )}

      <DealDetails open={detailsOpen} onOpenChange={setDetailsOpen} deal={deal} save={save} />
      <AgreeSheet key={`${deal.id}:${agreeOpen}`} open={agreeOpen} onOpenChange={setAgreeOpen} deal={deal} api={api} website={website}
        onDone={(r) => {
          if (deal.stage !== "agreed" && r.deal.stage === "agreed") {
            setCelebrate(true);
            setTimeout(() => setCelebrate(false), 1200);
          }
          onChange(r.deal);
          onProposals(r);
        }} />
    </div>
  );
}
