"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Handshake } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useApi } from "@/lib/api";
import { AddCreatorsDialog } from "@/components/deals/AddCreatorsDialog";
import { ContentList } from "@/components/deals/ContentList";
import { DealChat, askWords } from "@/components/deals/DealChat";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Segmented } from "@/components/ui/segmented";
import { GmailConnect, useGmail } from "@/components/GmailConnect";
import { type Deal, type DealsSummary, type Proposal, money } from "@/data/deals";
import { updatedLabel } from "@/types/campaign";

const TALKING = ["contacted", "negotiating"];
const CONTENT = ["agreed", "content", "live", "paid"];
const MESSAGE_KINDS = ["send_counter", "agree", "mark_lost", "follow_up"];

type Group = { key: string; label: string; items: Deal[]; folded?: boolean };

function ListItem({ d, active, yourTurn, onOpen }: { d: Deal; active: boolean; yourTurn: boolean; onOpen: () => void }) {
  const last = d.last_message;
  const sub = last ? `${last.who === "you" ? "You: " : ""}${last.text}` : d.quoted_rate != null ? `Asked ${askWords(d.quoted_rate, d.quoted_commission_pct)}` : "No messages yet";
  return (
    <button type="button" onClick={onOpen} aria-current={active}
      className={`w-full text-left px-3 py-2.5 flex items-start gap-2.5 rounded-md transition-colors ${active ? "bg-zinc-100 dark:bg-[#17181a]" : "hover:bg-zinc-50 dark:hover:bg-[#121314]"}`}>
      <CreatorAvatar name={d.name} src={d.avatar_url} className="w-8 h-8 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center shrink-0" textClassName="text-xs font-medium" />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className={`text-[13px] truncate ${yourTurn ? "font-semibold text-zinc-900 dark:text-zinc-100" : "font-medium text-zinc-800 dark:text-zinc-200"}`}>{d.name}</span>
          {yourTurn && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" aria-label="Your turn" />}
          <span className="ml-auto text-[10px] text-zinc-400 shrink-0">{last?.at ? updatedLabel(last.at) : ""}</span>
        </span>
        <span className="block text-[11px] text-zinc-500 truncate">{sub}</span>
      </span>
    </button>
  );
}

/** The Deals tab (spec §8.6b): Negotiating is an inbox (creators on the left, the conversation on the right),
 * Content tracks agreed creators from agreed to posted to paid. */
export default function DealsBoard({ campaignId, apiOverride }: {
  campaignId: string;
  apiOverride?: (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>; // test pages only
}) {
  const signedInApi = useApi();
  const api = apiOverride ?? signedInApi;
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [summary, setSummary] = useState<DealsSummary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [view, setView] = useState<"talk" | "content">("talk");
  const [openId, setOpenId] = useState<string | null>(null);
  const [showLost, setShowLost] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gmail = useGmail(apiOverride);

  const load = () =>
    api(`/api/campaigns/${campaignId}/deals`)
      .then((r) => {
        const d = r.data as { deals: Deal[]; summary: DealsSummary; proposals?: Proposal[] };
        setDeals(d.deals);
        setSummary(d.summary);
        setProposals(d.proposals ?? []);
      })
      .catch(() => setError("Couldn't load deals. Refresh to try again."));

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
  const turn = new Set(proposals.filter((p) => MESSAGE_KINDS.includes(p.kind)).map((p) => p.deal_id));
  const talking = (deals ?? []).filter((d) => TALKING.includes(d.stage));
  const content = (deals ?? []).filter((d) => CONTENT.includes(d.stage));
  const lost = (deals ?? []).filter((d) => d.stage === "lost");
  const byLatest = (a: Deal, b: Deal) => (b.last_message?.at ?? b.updated_at ?? "").localeCompare(a.last_message?.at ?? a.updated_at ?? "");
  const groups: Group[] = [
    { key: "turn", label: "Your turn", items: talking.filter((d) => turn.has(d.id)).sort(byLatest) },
    { key: "waiting", label: "Waiting for them", items: talking.filter((d) => !turn.has(d.id)).sort(byLatest) },
    { key: "agreed", label: "Agreed", items: content.sort(byLatest) },
    { key: "lost", label: "Lost", items: lost, folded: !showLost },
  ];
  const open = (deals ?? []).find((d) => d.id === openId) ?? groups[0].items[0] ?? groups[1].items[0] ?? null;
  const contentDue = content.filter((d) => d.stage !== "paid").length;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 px-1">
          <div className="flex items-center gap-3">
            <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100">Deals</h1>
            {deals && deals.length > 0 && (
              <Segmented label="View" value={view} onChange={setView}
                options={[{ value: "talk", label: "Negotiating", count: turn.size || undefined }, { value: "content", label: "Content", count: contentDue || undefined }]} />
            )}
          </div>
          <div className="flex items-center gap-2">
            <GmailConnect gmail={gmail} />
            <AddCreatorsDialog campaignId={campaignId} api={api} existing={existing} onAdded={() => load()} />
          </div>
        </div>

        {summary && deals && deals.length > 0 && (
          <p className="px-1 text-xs text-zinc-500 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span><span className="text-zinc-900 dark:text-zinc-100 font-medium">{talking.length}</span> talking</span>
            <span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span>
            <span><span className="text-zinc-900 dark:text-zinc-100 font-medium">{summary.agreed}</span> agreed</span>
            <span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span>
            <span className={summary.over_budget ? "text-rose-500" : ""}>
              <span className={`font-mono ${summary.over_budget ? "" : "text-zinc-900 dark:text-zinc-100"}`}>{money(summary.committed)}</span> committed
              {summary.budget ? <> of <span className="font-mono">{money(summary.budget)}</span>{summary.over_budget ? " (over budget)" : ""}</> : null}
            </span>
            {summary.committed > 0 && (
              <>
                <span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span>
                <span><span className="font-mono text-zinc-900 dark:text-zinc-100">{money(Math.max(0, summary.committed - summary.paid))}</span> to pay</span>
              </>
            )}
          </p>
        )}

        {error && <p className="text-xs text-rose-500 px-1">{error}</p>}

        {deals === null ? (
          <div className="h-[clamp(420px,calc(100vh-260px),760px)] rounded-lg bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse motion-reduce:animate-none" />
        ) : deals.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center py-16 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-[#0c0d0e]/50">
            <Handshake size={22} className="text-zinc-400 mb-3" />
            <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">No deals yet</p>
            <p className="text-xs text-zinc-500 mt-1 mb-4">Send a pitch from Outreach, or add the creators you&apos;re talking to.</p>
            <AddCreatorsDialog campaignId={campaignId} api={api} existing={existing} onAdded={() => load()} />
          </div>
        ) : view === "content" ? (
          <ContentList deals={content} api={api} proposals={proposals} onChange={replace} onRemove={remove} onProposals={onProposals}
            onOpenChat={(id) => { setOpenId(id); setView("talk"); }} />
        ) : (
          <div className="h-[clamp(420px,calc(100vh-260px),760px)] rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] overflow-hidden grid grid-cols-1 md:grid-cols-[300px_minmax(0,1fr)]">
            {/* the list */}
            <div className={`border-r border-zinc-200/70 dark:border-zinc-800/70 overflow-y-auto p-2 space-y-3 ${openId ? "hidden md:block" : ""}`}>
              {groups.map((g) => g.items.length > 0 && (
                <section key={g.key} className="space-y-0.5">
                  {g.key === "lost" ? (
                    <button type="button" onClick={() => setShowLost((v) => !v)} className="px-3 pt-1 text-[11px] font-medium text-zinc-500 flex items-center gap-1">
                      {g.label} ({g.items.length}) <ChevronDown size={11} className={showLost ? "rotate-180" : ""} />
                    </button>
                  ) : (
                    <p className="px-3 pt-1 text-[11px] font-medium text-zinc-500">{g.label} <span className="text-zinc-400">{g.items.length}</span></p>
                  )}
                  {!g.folded && g.items.map((d) => (
                    <ListItem key={d.id} d={d} active={open?.id === d.id} yourTurn={turn.has(d.id)} onOpen={() => setOpenId(d.id)} />
                  ))}
                </section>
              ))}
            </div>
            {/* the conversation */}
            <div className={`min-h-0 min-w-0 ${openId ? "" : "hidden md:block"}`}>
              {open ? (
                <DealChat key={open.id} deal={open} api={api} gmailReady={gmail.ready}
                  proposals={proposals.filter((p) => p.deal_id === open.id && MESSAGE_KINDS.includes(p.kind))}
                  onChange={replace} onProposals={onProposals} onRemove={() => remove(open)} onBack={() => setOpenId(null)} />
              ) : (
                <p className="h-full flex items-center justify-center text-xs text-zinc-500">Pick a creator to see the conversation.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
