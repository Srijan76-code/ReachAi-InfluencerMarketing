"use client";

import { AlertCircle, CalendarClock, MoreHorizontal } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { type Deal, type Stage, STAGES, STAGE_LABEL, money } from "@/data/deals";

/** Price vs fair: green within, amber above, red far above (more than 2× the fair top). */
export function PriceVsFair({ deal }: { deal: Deal }) {
  const price = deal.agreed_rate ?? deal.quoted_rate;
  const v = deal.advice.verdict;
  const tone =
    v === "great" || v === "accept" ? "text-emerald-600 dark:text-emerald-400" : v === "counter" ? "text-amber-600 dark:text-amber-400" : v === "walk_away" ? "text-rose-500" : "text-zinc-700 dark:text-zinc-300";
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      {price != null ? (
        <span className={`font-mono text-[12px] font-semibold ${tone}`}>
          {money(price)}
          {deal.agreed_rate == null && deal.quoted_commission_pct ? ` + ${deal.quoted_commission_pct}%`
            : deal.agreed_rate != null && deal.commission_pct && deal.deal_type !== "flat" ? ` + ${deal.commission_pct}%` : ""}
        </span>
      ) : (
        <span className="text-[11px] text-zinc-500">No price yet</span>
      )}
      {deal.advice.fair_high != null && (
        <span className="text-[11px] text-zinc-500 truncate">
          Fair <span className="font-mono">{money(deal.advice.fair_low)}–{money(deal.advice.fair_high)}</span>
        </span>
      )}
    </div>
  );
}

function dueLabel(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function DealCard({ deal, onOpen, onMove, dragging, todo }: {
  deal: Deal;
  todo?: boolean; // has a suggested next step waiting
  onOpen: () => void;
  onMove: (stage: Stage) => void;
  dragging: boolean;
}) {
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/deal-id", deal.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onClick={onOpen}
      onKeyDown={(e) => e.key === "Enter" && onOpen()}
      role="button"
      tabIndex={0}
      aria-label={`${deal.name}, ${STAGE_LABEL[deal.stage]}`}
      className={`group rounded-lg border bg-white dark:bg-[#0c0d0e] p-2.5 space-y-2 cursor-grab active:cursor-grabbing transition-colors ${dragging ? "opacity-40" : ""} ${deal.overdue ? "border-rose-500/40" : "border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700"}`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <CreatorAvatar
          name={deal.name}
          src={deal.avatar_url}
          className="w-7 h-7 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center shrink-0"
          textClassName="text-[11px] font-medium"
        />
        <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate flex-1" title={deal.name}>{deal.name}</span>
        {todo && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" title="Has a next step in To do" aria-label="Has a next step" />}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" onClick={(e) => e.stopPropagation()} aria-label={`Move ${deal.name}`} className="h-6 w-6 shrink-0 flex items-center justify-center rounded text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 opacity-0 group-hover:opacity-100 focus:opacity-100">
              <MoreHorizontal size={14} />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuLabel className="text-[11px] text-zinc-500">Move to</DropdownMenuLabel>
            {STAGES.filter((s) => s !== deal.stage).map((s, i) => (
              <div key={s}>
                {s === "lost" && i > 0 && <DropdownMenuSeparator />}
                <DropdownMenuItem className={`text-xs cursor-pointer ${s === "lost" ? "text-rose-500 focus:text-rose-500" : ""}`} onSelect={() => onMove(s)}>
                  {STAGE_LABEL[s]}
                </DropdownMenuItem>
              </div>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <PriceVsFair deal={deal} />
      {(deal.post_by || deal.overdue) && (
        <p className={`flex items-center gap-1 text-[11px] ${deal.overdue ? "text-rose-500 font-medium" : "text-zinc-500"}`}>
          {deal.overdue ? <AlertCircle size={11} /> : <CalendarClock size={11} />}
          {deal.overdue ? `Post was due ${dueLabel(deal.post_by!)}` : `Post by ${dueLabel(deal.post_by!)}`}
        </p>
      )}
    </div>
  );
}
