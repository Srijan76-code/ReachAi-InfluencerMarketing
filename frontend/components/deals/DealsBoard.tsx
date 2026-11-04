"use client";

import { useEffect, useMemo, useState } from "react";
import { Handshake } from "lucide-react";
import { Sheet } from "@/components/ui/sheet";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useApi } from "@/lib/api";
import { btn } from "@/lib/ui";
import { StatStrip, StatTile } from "@/components/ui/stat";
import { AddCreatorsDialog } from "@/components/deals/AddCreatorsDialog";
import { DealCard } from "@/components/deals/DealCard";
import { DealPanel } from "@/components/deals/DealPanel";
import { NeedsYou } from "@/components/deals/NeedsYou";
import { Segmented } from "@/components/ui/segmented";
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
          <AddCreatorsDialog campaignId={campaignId} api={api} existing={existing} onAdded={() => load()} />
        </div>

        {error && <p className="text-xs text-rose-500 px-1">{error}</p>}

        {summary && deals && deals.length > 0 && (
          <StatStrip>
            <StatTile label="Deals" value={<span className="font-mono">{summary.deals}</span>} sub={`${summary.agreed} agreed`} />
            <StatTile
              label="Committed"
              value={<span className="font-mono">{money(summary.committed)}</span>}
              sub={summary.budget ? `of ${money(summary.budget)} budget${summary.over_budget ? " · over budget" : ""}` : "agreed prices"}
              tone={summary.over_budget ? "bad" : undefined}
            />
            <StatTile label="Posts live" value={<span className="font-mono">{summary.live} / {summary.agreed}</span>} sub="of agreed deals" />
            <StatTile label="Paid" value={<span className="font-mono">{money(summary.paid)}</span>} sub={summary.committed ? `${money(Math.max(0, summary.committed - summary.paid))} still to pay` : undefined} />
          </StatStrip>
        )}

        {deals && deals.length > 0 && view === "todo" ? (
          <NeedsYou proposals={proposals} api={api} onDone={onProposals} onOpen={setOpenId} />
        ) : deals === null ? (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {BOARD_STAGES.map((s) => <div key={s} className="h-40 rounded-lg bg-zinc-200/50 dark:bg-zinc-800/50 animate-pulse motion-reduce:animate-none" />)}
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
            <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(160px, 1fr))` }}>
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
                    className={`rounded-lg border p-2 space-y-2 min-h-40 transition-colors ${over === stage ? "border-zinc-400 dark:border-zinc-500 bg-zinc-100/80 dark:bg-zinc-900/80" : "border-zinc-200/70 dark:border-zinc-800/70 bg-zinc-50 dark:bg-[#0a0b0c]"}`}
                  >
                    <div className="flex items-baseline justify-between gap-2 px-1 pt-0.5">
                      <span className="text-xs font-medium text-zinc-900 dark:text-zinc-100">{STAGE_LABEL[stage]}</span>
                      <span className="text-[11px] font-mono text-zinc-500">{items.length}</span>
                    </div>
                    <p className="px-1 -mt-1.5 text-[11px] text-zinc-500 truncate">{STAGE_HINT[stage]}</p>
                    {items.map((d) => (
                      <div key={d.id} onDragStart={() => setDragging(d.id)} onDragEnd={() => { setDragging(null); setOver(null); }}>
                        <DealCard deal={d} todo={todoDeals.has(d.id)} dragging={dragging === d.id} onOpen={() => setOpenId(d.id)} onMove={(s) => move(d, s)} />
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <Sheet open={!!open} onOpenChange={(o) => !o && setOpenId(null)}>
          {open && <DealPanel deal={open} api={api} onChange={replace} onRemove={() => remove(open)} proposals={proposals.filter((p) => p.deal_id === open.id)} onProposals={onProposals} />}
        </Sheet>
      </div>
    </TooltipProvider>
  );
}
