"use client";

import { useEffect, useMemo, useState } from "react";
import { Handshake } from "lucide-react";
import { Sheet } from "@/components/ui/sheet";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useApi } from "@/lib/api";
import { btn } from "@/lib/ui";
import { AddCreatorsDialog } from "@/components/deals/AddCreatorsDialog";
import { DealCard } from "@/components/deals/DealCard";
import { DealPanel } from "@/components/deals/DealPanel";
import { NeedsYou } from "@/components/deals/NeedsYou";
import { Segmented } from "@/components/ui/segmented";
import { GmailConnect, useGmail } from "@/components/GmailConnect";
import { BOARD_STAGES, type Deal, type DealsSummary, type Proposal, STAGE_HINT, STAGE_LABEL, type Stage, money } from "@/data/deals";

/** The Deals tab (spec §8.1, §8.5): one column per stage, drag cards to move them, click to open. */
export default function DealsBoard({ campaignId, apiOverride }: {
  campaignId: string;
  apiOverride?: (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>; // test pages only
}) {
  const signedInApi = useApi();
  const api = apiOverride ?? signedInApi;
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [summary, setSummary] = useState<DealsSummary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [view, setView] = useState<"board" | "todo">("board");
  const gmail = useGmail(apiOverride);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [showLost, setShowLost] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<Stage | null>(null);

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
    // then check email threads for new replies, without holding up the board
    api(`/api/campaigns/${campaignId}/gmail/sync`, { method: "POST" })
      .then((r) => {
        if ((r.data as { new?: number })?.new) load();
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [campaignId]);

  const replace = (d: Deal) => {
    setDeals((ds) => (ds ? ds.map((x) => (x.id === d.id ? d : x)) : ds));
    load(); // summary (committed, paid…) is computed on the server
  };

  const move = async (deal: Deal, stage: Stage) => {
    if (deal.stage === stage) return;
    const before = deals;
    setDeals((ds) => ds?.map((x) => (x.id === deal.id ? { ...x, stage } : x)) ?? ds); // optimistic
    try {
      const r = await api(`/api/deals/${deal.id}`, { method: "PATCH", data: { stage } });
      replace(r.data as Deal);
    } catch {
      setDeals(before);
      setError("Couldn't move that deal. Try again.");
    }
  };

  const remove = async (deal: Deal) => {
    setOpenId(null);
    setDeals((ds) => ds?.filter((x) => x.id !== deal.id) ?? ds);
    try {
      await api(`/api/deals/${deal.id}`, { method: "DELETE" });
      load();
    } catch {
      load();
    }
  };

  // a suggestion was approved or skipped (or a reply was read): show the new list, then reload the deals it changed
  const onProposals = (data: { proposals?: Proposal[] }) => {
    if (data.proposals) setProposals(data.proposals);
    load();
  };

  const existing = useMemo(() => new Set((deals ?? []).map((d) => d.creator_id)), [deals]);
  const columns: Stage[] = showLost ? [...BOARD_STAGES, "lost"] : BOARD_STAGES;
  const lostCount = deals?.filter((d) => d.stage === "lost").length ?? 0;
  const open = deals?.find((d) => d.id === openId) ?? null;
  const todoDeals = new Set(proposals.map((p) => p.deal_id));

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-5">
        <div className="flex items-center justify-between gap-3 px-1">
          <div className="flex items-center gap-3">
            <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100">Deals</h1>
            {deals && deals.length > 0 && (
              <Segmented
                label="View"
                value={view}
                onChange={setView}
                options={[{ value: "board", label: "Board" }, { value: "todo", label: "To do", count: proposals.length }]}
              />
            )}
            {view === "board" && lostCount > 0 && (
              <button type="button" onClick={() => setShowLost((v) => !v)} className={btn}>
                {showLost ? "Hide lost" : `Show lost (${lostCount})`}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <GmailConnect gmail={gmail} />
            <AddCreatorsDialog campaignId={campaignId} api={api} existing={existing} onAdded={() => load()} />
          </div>
        </div>

        {error && <p className="text-xs text-rose-500 px-1">{error}</p>}

        {summary && deals && deals.length > 0 && (
          <p className="px-1 text-xs text-zinc-500 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span><span className="text-zinc-900 dark:text-zinc-100 font-medium">{summary.deals}</span> deals</span>
            <span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span>
            <span className={summary.over_budget ? "text-rose-500" : ""}>
              <span className={`font-mono ${summary.over_budget ? "" : "text-zinc-900 dark:text-zinc-100"}`}>{money(summary.committed)}</span> committed
              {summary.budget ? <> of <span className="font-mono">{money(summary.budget)}</span>{summary.over_budget ? " (over budget)" : ""}</> : null}
            </span>
            <span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span>
            <span><span className="font-mono text-zinc-900 dark:text-zinc-100">{summary.live}</span> of {summary.agreed} posts live</span>
            {summary.committed > 0 && (
              <>
                <span aria-hidden className="text-zinc-300 dark:text-zinc-700">·</span>
                <span><span className="font-mono text-zinc-900 dark:text-zinc-100">{money(Math.max(0, summary.committed - summary.paid))}</span> to pay</span>
              </>
            )}
          </p>
        )}

        {deals && deals.length > 0 && view === "todo" ? (
          <NeedsYou proposals={proposals} api={api} onDone={onProposals} onOpen={setOpenId} />
        ) : deals === null ? (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {BOARD_STAGES.map((s) => <div key={s} className="h-[clamp(360px,calc(100vh-300px),640px)] rounded-lg bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse motion-reduce:animate-none" />)}
          </div>
        ) : deals.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center py-16 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-[#0c0d0e]/50">
            <Handshake size={22} className="text-zinc-400 mb-3" />
            <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">No deals yet</p>
            <p className="text-xs text-zinc-500 mt-1 mb-4">Add the creators you&apos;re talking to and track them from first message to paid.</p>
            <AddCreatorsDialog campaignId={campaignId} api={api} existing={existing} onAdded={() => load()} />
          </div>
        ) : (
          <div className="overflow-x-auto pb-2 -mx-1 px-1">
            <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(196px, 1fr))` }}>
              {columns.map((stage) => {
                const items = deals.filter((d) => d.stage === stage);
                return (
                  <div
                    key={stage}
                    onDragOver={(e) => {
                      if (!e.dataTransfer.types.includes("text/deal-id")) return;
                      e.preventDefault();
                      setOver(stage);
                    }}
                    onDragLeave={() => setOver((o) => (o === stage ? null : o))}
                    onDrop={(e) => {
                      e.preventDefault();
                      setOver(null);
                      const id = e.dataTransfer.getData("text/deal-id");
                      const d = deals.find((x) => x.id === id);
                      if (d) move(d, stage);
                      setDragging(null);
                    }}
                    className={`rounded-lg border flex flex-col h-[clamp(360px,calc(100vh-300px),640px)] transition-colors ${over === stage ? "border-zinc-400 dark:border-zinc-500 bg-zinc-100/80 dark:bg-zinc-900/80" : "border-zinc-200/70 dark:border-zinc-800/70 bg-zinc-50 dark:bg-[#0a0b0c]"}`}
                  >
                    <div className="px-3 pt-2.5 pb-2 border-b border-zinc-200/60 dark:border-zinc-800/60 shrink-0">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-xs font-medium text-zinc-900 dark:text-zinc-100">{STAGE_LABEL[stage]}</span>
                        <span className="text-[11px] font-mono text-zinc-500">{items.length}</span>
                      </div>
                      <p className="text-[11px] text-zinc-500 truncate">{STAGE_HINT[stage]}</p>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2 [scrollbar-width:thin]">
                      {items.map((d) => (
                        <div key={d.id} onDragStart={() => setDragging(d.id)} onDragEnd={() => { setDragging(null); setOver(null); }}>
                          <DealCard deal={d} todo={todoDeals.has(d.id)} dragging={dragging === d.id} onOpen={() => setOpenId(d.id)} onMove={(s) => move(d, s)} />
                        </div>
                      ))}
                      {items.length === 0 && <p className="text-[11px] text-zinc-400 dark:text-zinc-600 text-center pt-6">Drop a deal here</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <Sheet open={!!open} onOpenChange={(o) => !o && setOpenId(null)}>
          {open && <DealPanel deal={open} api={api} onChange={replace} onRemove={() => remove(open)} proposals={proposals.filter((p) => p.deal_id === open.id)} onProposals={onProposals} gmailReady={gmail.ready} />}
        </Sheet>
      </div>
    </TooltipProvider>
  );
}
