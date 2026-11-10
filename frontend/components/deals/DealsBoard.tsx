"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react";
import { ChevronDown, Loader2, PanelLeftClose, PanelLeftOpen, Search, Send } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useApi } from "@/lib/api";
import { useInbox } from "@/lib/inbox";
import { AddCreatorsDialog } from "@/components/deals/AddCreatorsDialog";
import { DealChat, askWords } from "@/components/deals/DealChat";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { GmailConnect, useGmail } from "@/components/GmailConnect";
import { CHAT_KINDS, type Deal, type DealsSummary, type Proposal, money } from "@/data/deals";
import { updatedLabel } from "@/types/campaign";

const TALKING = ["contacted", "negotiating"];
const CONTENT = ["agreed", "content", "live", "paid"];
const HEIGHT = "h-[calc(100dvh-200px)] md:h-[calc(100dvh-178px)] min-h-[480px]";

type Group = { key: string; label: string; items: Deal[]; folded?: boolean };

function ListItem({ d, active, draft, compact, onOpen }: { d: Deal; active: boolean; draft: Proposal | undefined; compact: boolean; onOpen: () => void }) {
  const reduce = useReducedMotion();
  const last = d.last_message;
  const unread = d.unread ?? 0;
  const sub = d.writing && !draft ? "Writing a first message…"
    : draft && !unread ? (draft.kind === "pitch" ? "First message ready to check" : draft.kind === "confirm_terms" ? "Confirmation ready to send" : "ReachAI drafted a reply")
    : last ? `${last.who === "you" ? "You: " : ""}${last.text}`
    : d.quoted_rate != null ? `Asked ${askWords(d.quoted_rate, d.quoted_commission_pct)}` : "No messages yet";
  return (
    <motion.li layout={!reduce} transition={{ type: "spring", stiffness: 500, damping: 40 }}>
      <button type="button" onClick={onOpen} aria-current={active} title={compact ? d.name : undefined}
        className={`relative w-full text-left rounded-lg transition-colors flex items-center ${compact ? "justify-center p-1.5" : "gap-2.5 px-2.5 py-2"}
          ${active ? "bg-zinc-100 dark:bg-[#17181a]" : "hover:bg-zinc-50 dark:hover:bg-[#121314]"}`}>
        {active && !compact && <motion.span layoutId="chat-active" className="absolute left-0 top-2 bottom-2 w-[2px] rounded-full bg-zinc-900 dark:bg-zinc-100" />}
        <span className="relative shrink-0">
          <CreatorAvatar name={d.name} src={d.avatar_url} className="w-9 h-9 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center" textClassName="text-xs font-medium" />
          {compact && (unread > 0 || draft) && <span className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-white dark:ring-[#0c0d0e] ${unread ? "bg-blue-500" : "bg-violet-500"}`} />}
        </span>
        {!compact && (
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2">
              <span className={`text-[13px] truncate ${unread || draft ? "font-semibold text-zinc-900 dark:text-zinc-100" : "font-medium text-zinc-700 dark:text-zinc-300"}`}>{d.name}</span>
              <span className="ml-auto text-[10px] text-zinc-400 shrink-0">{last?.at ? updatedLabel(last.at) : ""}</span>
            </span>
            <span className="flex items-center gap-2">
              <span className={`block text-[11px] truncate flex-1 ${draft && !unread ? "text-violet-600 dark:text-violet-400" : unread ? "text-zinc-700 dark:text-zinc-300" : "text-zinc-500"}`}>{sub}</span>
              <AnimatePresence>
                {unread > 0 && (
                  <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={{ type: "spring", stiffness: 500, damping: 25 }}
                    className="min-w-4 h-4 px-1 rounded-full bg-blue-500 text-white text-[10px] font-medium flex items-center justify-center shrink-0" aria-label={`${unread} unread`}>
                    {unread}
                  </motion.span>
                )}
              </AnimatePresence>
            </span>
          </span>
        )}
      </button>
    </motion.li>
  );
}

/** The Deals tab (spec §8.6b): Negotiating is an inbox (creators on the left, the conversation filling the rest),
 * Content tracks agreed creators from agreed to posted to paid. */
export default function DealsBoard({ campaignId, apiOverride }: {
  campaignId: string;
  apiOverride?: (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>; // test pages only
}) {
  const signedInApi = useApi();
  const api = apiOverride ?? signedInApi;
  const router = useRouter();
  const params = useSearchParams();
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [summary, setSummary] = useState<DealsSummary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [showLost, setShowLost] = useState(false);
  const [compact, setCompact] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [website, setWebsite] = useState<string | null>(null);
  const [bulk, setBulk] = useState<"idle" | "busy">("idle");
  const [bulkNote, setBulkNote] = useState<string | null>(null);
  const gmail = useGmail(apiOverride);
  const openId = params?.get("chat") ?? null;
  const waiting = useInbox().by_campaign[campaignId];

  const setOpenId = (id: string | null) => {
    const p = new URLSearchParams(params?.toString() ?? "");
    if (id) p.set("chat", id);
    else p.delete("chat");
    router.replace(`?${p.toString()}`, { scroll: false });
  };

  const load = () =>
    api(`/api/campaigns/${campaignId}/deals`)
      .then((r) => {
        const d = r.data as { deals: Deal[]; summary: DealsSummary; proposals?: Proposal[]; website?: string | null };
        setDeals(d.deals);
        setWebsite(d.website ?? null);
        setSummary(d.summary);
        setProposals(d.proposals ?? []);
        setError(null);
      })
      .catch(() => setError("Couldn't load. Refresh to try again."));

  useEffect(() => {
    load();
    // then check email threads for new replies, without holding up the page
    api(`/api/campaigns/${campaignId}/gmail/sync`, { method: "POST" })
      .then((r) => {
        if ((r.data as { new?: number })?.new) load();
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [campaignId]);

  // first messages being written: check every few seconds until they land
  const writingNow = (deals ?? []).some((d) => d.writing);
  useEffect(() => {
    if (!writingNow) return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [writingNow]);

  // a new reply found by the background check (the bell's poll): show it
  const unreadNow = waiting?.unread ?? 0;
  useEffect(() => {
    if (unreadNow) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when the count changes
  }, [unreadNow]);

  const replace = (d: Deal) => {
    setDeals((ds) => (ds ? ds.map((x) => (x.id === d.id ? { ...x, ...d } : x)) : ds));
    load();
  };
  const onProposals = (data: { proposals?: Proposal[] }) => {
    if (data.proposals) setProposals(data.proposals);
    load();
  };
  const remove = async (deal: Deal) => {
    setOpenId(null);
    setDeals((ds) => ds?.filter((x) => x.id !== deal.id) ?? ds);
    try {
      await api(`/api/deals/${deal.id}`, { method: "DELETE" });
    } finally {
      load();
    }
  };

  const existing = useMemo(() => new Set((deals ?? []).map((d) => d.creator_id)), [deals]);
  const draftOf = new Map(proposals.filter((p) => CHAT_KINDS.includes(p.kind)).map((p) => [p.deal_id, p] as const));
  const drafts = new Set(draftOf.keys());
  const byId = new Map((deals ?? []).map((d) => [d.id, d] as const));
  // first emails you've opened and looked at: "Send N reviewed" sends them from Gmail in one go
  const reviewed = proposals.filter((p) => p.kind === "pitch" && p.seen && p.can_send && byId.get(p.deal_id)?.channel === "email");
  const sendReviewed = async () => {
    setBulk("busy");
    setBulkNote(null);
    try {
      const r = (await api(`/api/campaigns/${campaignId}/pitches/send`, { method: "POST", data: { proposal_ids: reviewed.map((p) => p.id) } })).data as
        { sent: number; skipped: { name: string; why: string }[]; proposals?: Proposal[] };
      setBulkNote(`Sent ${r.sent}${r.skipped.length ? `. Not sent: ${r.skipped.map((x) => `${x.name} (${x.why.replace(/\.$/, "")})`).join(", ")}` : ""}`);
      onProposals(r);
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setBulkNote(typeof d === "string" ? d : "Couldn't send. Try again");
    } finally {
      setBulk("idle");
    }
  };
  const q = query.trim().toLowerCase();
  const all = (deals ?? []).filter((d) => !q || d.name.toLowerCase().includes(q));
  const talking = all.filter((d) => TALKING.includes(d.stage));
  const byLatest = (a: Deal, b: Deal) => (b.last_message?.at ?? b.updated_at ?? "").localeCompare(a.last_message?.at ?? a.updated_at ?? "");
  const yourTurn = (d: Deal) => drafts.has(d.id) || (d.unread ?? 0) > 0 || !!d.writing;
  const groups: Group[] = [
    { key: "turn", label: "Your turn", items: all.filter((d) => d.stage !== "lost" && yourTurn(d)).sort(byLatest) },
    { key: "waiting", label: "Waiting for them", items: talking.filter((d) => !yourTurn(d)).sort(byLatest) },
    { key: "agreed", label: "Agreed", items: all.filter((d) => CONTENT.includes(d.stage) && !yourTurn(d)).sort(byLatest) },
    { key: "lost", label: "Lost", items: all.filter((d) => d.stage === "lost"), folded: !showLost && !q },
  ];
  const open = (deals ?? []).find((d) => d.id === openId) ?? groups[0].items[0] ?? groups[1].items[0] ?? groups[2].items[0] ?? null;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-3 md:-mx-8 md:-mt-8">
        <div className="flex flex-wrap items-center justify-between gap-3 px-1">
          <div className="flex items-center gap-3 min-w-0">
            <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100">Outreach</h1>
            {summary && deals && deals.length > 0 && (
              <span className={`hidden lg:inline-flex items-center gap-1.5 h-[30px] px-2.5 rounded-md text-[11px] ${summary.over_budget ? "text-rose-500" : "text-zinc-500"}`}>
                <span className="font-mono text-zinc-900 dark:text-zinc-100">{summary.agreed}</span> agreed
                <span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span>
                <span className="font-mono text-zinc-900 dark:text-zinc-100">{money(summary.committed)}</span>
                {summary.budget ? <>of <span className="font-mono">{money(summary.budget)}</span></> : "committed"}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {bulkNote && <span className="text-[11px] text-zinc-500 max-w-[280px] truncate" title={bulkNote}>{bulkNote}</span>}
            {reviewed.length > 1 && (
              <button type="button" onClick={sendReviewed} disabled={bulk === "busy"} className="inline-flex items-center gap-1.5 h-[30px] px-3 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40"
                title="Sends the first emails you've opened and checked, from your Gmail">
                {bulk === "busy" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Send {reviewed.length} checked
              </button>
            )}
            <GmailConnect gmail={gmail} />
            <AddCreatorsDialog campaignId={campaignId} api={api} existing={existing} onAdded={() => load()} />
          </div>
        </div>

        {error && <p className="text-xs text-rose-500 px-1">{error}</p>}

        {deals === null ? (
          <div className={`${HEIGHT} rounded-xl border border-zinc-200 dark:border-zinc-800 grid grid-cols-1 md:grid-cols-[300px_minmax(0,1fr)] overflow-hidden`}>
            <div className="p-3 space-y-2 border-r border-zinc-200/70 dark:border-zinc-800/70">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-12 rounded-lg bg-zinc-100 dark:bg-[#141517] animate-pulse motion-reduce:animate-none" />)}
            </div>
            <div className="hidden md:block" />
          </div>
        ) : deals.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center py-20 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800">
            <Send size={22} className="text-zinc-400 mb-3" />
            <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">No one to talk to yet</p>
            <p className="text-xs text-zinc-500 mt-1 mb-4">Add creators from your shortlist. ReachAI drafts a first message for each, in their own chat.</p>
            <AddCreatorsDialog campaignId={campaignId} api={api} existing={existing} onAdded={() => load()} />
          </div>
        ) : (
          <div className={`${HEIGHT} rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] overflow-hidden grid grid-cols-1
            ${compact ? "md:grid-cols-[64px_minmax(0,1fr)]" : "md:grid-cols-[300px_minmax(0,1fr)]"} transition-[grid-template-columns] duration-300`}>
            {/* the list */}
            <div className={`border-r border-zinc-200/70 dark:border-zinc-800/70 min-h-0 flex flex-col ${openId ? "hidden md:flex" : "flex"}`}>
              <div className={`h-16 shrink-0 flex items-center gap-1.5 border-b border-zinc-200/70 dark:border-zinc-800/70 ${compact ? "justify-center px-2" : "px-3"}`}>
                {!compact && (
                  <label className="flex-1 flex items-center gap-2 h-8 px-2.5 rounded-lg bg-zinc-100/80 dark:bg-[#141517] text-zinc-500">
                    <Search size={13} />
                    <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search creators" aria-label="Search creators"
                      className="flex-1 min-w-0 bg-transparent text-xs text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none" />
                  </label>
                )}
                <button type="button" onClick={() => setCompact((v) => !v)} aria-label={compact ? "Show names" : "Show photos only"}
                  className="hidden md:flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800">
                  {compact ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
                </button>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-4">
                <LayoutGroup>
                  {groups.map((g) => g.items.length > 0 && (
                    <section key={g.key} className="space-y-0.5">
                      {!compact && (g.key === "lost" ? (
                        <button type="button" onClick={() => setShowLost((v) => !v)} className="px-2.5 pb-1 text-[11px] font-medium text-zinc-500 flex items-center gap-1">
                          {g.label} {g.items.length} <ChevronDown size={11} className={`transition-transform ${showLost ? "rotate-180" : ""}`} />
                        </button>
                      ) : (
                        <p className="px-2.5 pb-1 text-[11px] font-medium text-zinc-500">{g.label} <span className="text-zinc-400">{g.items.length}</span></p>
                      ))}
                      {compact && g.key !== "turn" && <div className="mx-3 my-2 h-px bg-zinc-200/70 dark:bg-zinc-800/70" />}
                      {!g.folded && (
                        <ul className="space-y-0.5">
                          {g.items.map((d) => (
                            <ListItem key={d.id} d={d} active={open?.id === d.id} draft={draftOf.get(d.id)} compact={compact} onOpen={() => setOpenId(d.id)} />
                          ))}
                        </ul>
                      )}
                    </section>
                  ))}
                </LayoutGroup>
                {q && all.length === 0 && <p className="px-2.5 py-6 text-center text-xs text-zinc-500">No one called &ldquo;{query}&rdquo;</p>}
              </div>
            </div>
            {/* the conversation */}
            <div className={`min-h-0 min-w-0 ${openId ? "" : "hidden md:block"}`}>
              <AnimatePresence mode="wait" initial={false}>
                {open ? (
                  <motion.div key={open.id} className="h-full" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
                    <DealChat deal={open} api={api} gmailReady={gmail.ready} website={website} onReconnect={() => gmail.connect()}
                      proposals={proposals.filter((p) => p.deal_id === open.id && CHAT_KINDS.includes(p.kind))}
                      onChange={replace} onProposals={onProposals} onRemove={() => remove(open)} onBack={() => setOpenId(null)}
                      onRead={() => setDeals((ds) => ds?.map((x) => (x.id === open.id ? { ...x, unread: 0 } : x)) ?? ds)} />
                  </motion.div>
                ) : (
                  <p className="h-full flex items-center justify-center text-xs text-zinc-500">Pick a creator to see the conversation.</p>
                )}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
