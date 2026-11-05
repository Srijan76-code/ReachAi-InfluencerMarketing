"use client";

import { useState } from "react";
import { AlertCircle, Check, ExternalLink, Loader2, MoreHorizontal } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ProposalCard } from "@/components/deals/NeedsYou";
import { askWords } from "@/components/deals/DealChat";
import { btn, btnPrimary, control } from "@/lib/ui";
import { type Deal, type Proposal, money } from "@/data/deals";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

const STEPS = ["Agreed", "Posted", "Paid"] as const;
const stepOf = (d: Deal) => (d.stage === "paid" ? 2 : d.stage === "live" ? 1 : 0);
const day = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

function errorText(e: unknown, fallback: string) {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

function Row({ deal, api, onChange, onBack, onRemove, chase, onProposals }: {
  deal: Deal;
  api: Api;
  onChange: (d: Deal) => void;
  onBack: () => void;
  onRemove: () => void;
  chase?: Proposal; // ReachAI's reminder about a late post
  onProposals: (data: { proposals?: Proposal[] }) => void;
}) {
  const [link, setLink] = useState("");
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nudge, setNudge] = useState(false);
  const step = stepOf(deal);

  const save = async (patch: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      onChange((await api(`/api/deals/${deal.id}`, { method: "PATCH", data: patch })).data as Deal);
      setAdding(false);
      setLink("");
    } catch (e) {
      setError(errorText(e, "Couldn't save that."));
    } finally {
      setBusy(false);
    }
  };

  const price = deal.agreed_rate != null ? askWords(deal.agreed_rate, deal.deal_type !== "flat" ? deal.commission_pct : null) : "—";

  return (
    <li className="px-4 py-3 flex flex-col gap-2 md:flex-row md:items-center md:gap-5">
      <div className="flex items-center gap-3 min-w-0 md:w-[260px] shrink-0">
        <CreatorAvatar name={deal.name} src={deal.avatar_url} className="w-8 h-8 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center shrink-0" textClassName="text-xs font-medium" />
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate">{deal.name}</p>
          <p className="text-[11px] text-zinc-500 font-mono">{price}</p>
        </div>
      </div>

      {/* progress */}
      <ol className="flex items-center gap-1.5 shrink-0" aria-label={`Step ${step + 1} of 3: ${STEPS[step]}`}>
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-1.5">
            <span className={`flex items-center gap-1 text-[11px] ${i <= step ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-400 dark:text-zinc-600"}`}>
              <span className={`w-4 h-4 rounded-full flex items-center justify-center border ${i <= step ? "bg-zinc-900 border-zinc-900 text-white dark:bg-zinc-100 dark:border-zinc-100 dark:text-zinc-900" : "border-zinc-300 dark:border-zinc-700"}`}>
                {i <= step && <Check size={10} strokeWidth={3} />}
              </span>
              {s}
            </span>
            {i < STEPS.length - 1 && <span className={`w-6 h-px ${i < step ? "bg-zinc-900 dark:bg-zinc-100" : "bg-zinc-200 dark:bg-zinc-800"}`} />}
          </li>
        ))}
      </ol>

      {/* status + the one next action */}
      <div className="flex items-center gap-2 min-w-0 md:flex-1 md:justify-end">
        {step === 0 && !adding && (
          <>
            <span className={`text-[11px] truncate flex items-center gap-1 ${deal.overdue ? "text-rose-500" : "text-zinc-500"}`}>
              {deal.overdue && <AlertCircle size={11} />}
              {deal.post_by ? (deal.overdue ? `Was due ${day(deal.post_by)}` : `Post by ${day(deal.post_by)}`) : (
                <label className="flex items-center gap-1.5">Post by
                  <input type="date" aria-label="Post by" onChange={(e) => e.target.value && save({ post_by: e.target.value })} className={`${control} h-[26px] w-[130px] [color-scheme:light] dark:[color-scheme:dark]`} />
                </label>
              )}
            </span>
            {chase && <button type="button" onClick={() => setNudge(true)} className={btn}>Send a reminder</button>}
            <button type="button" onClick={() => setAdding(true)} className={btnPrimary}>Add post link</button>
          </>
        )}
        {step === 0 && adding && (
          <>
            <input autoFocus value={link} onChange={(e) => setLink(e.target.value)} onKeyDown={(e) => e.key === "Enter" && link.trim() && save({ post_url: link.trim(), stage: "live" })}
              placeholder="https://youtube.com/watch?v=…" aria-label="Link to the live post" className={`${control} md:max-w-[280px]`} />
            <button type="button" onClick={() => save({ post_url: link.trim(), stage: "live" })} disabled={busy || !link.trim()} className={btnPrimary}>
              {busy && <Loader2 size={13} className="animate-spin" />} Save
            </button>
            <button type="button" onClick={() => setAdding(false)} className={btn}>Cancel</button>
          </>
        )}
        {step === 1 && (
          <>
            {deal.post_url && <a href={deal.post_url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 flex items-center gap-1">View post <ExternalLink size={11} /></a>}
            <button type="button" onClick={() => save({ stage: "paid" })} disabled={busy} className={btnPrimary}>
              {busy && <Loader2 size={13} className="animate-spin" />} Mark paid{deal.agreed_rate ? ` (${money(deal.agreed_rate)})` : ""}
            </button>
          </>
        )}
        {step === 2 && (
          <span className="text-[11px] text-emerald-600 dark:text-emerald-400">Paid {money(deal.paid_amount)}{deal.paid_at ? ` on ${new Date(deal.paid_at).toLocaleDateString()}` : ""}</span>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" aria-label={`More for ${deal.name}`} className="h-[30px] w-[30px] shrink-0 flex items-center justify-center rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800"><MoreHorizontal size={16} /></button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
            <DropdownMenuItem className="text-xs cursor-pointer" onSelect={onBack}>Open the conversation</DropdownMenuItem>
            {step > 0 && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => save({ stage: step === 2 ? "live" : "agreed" })}>Undo last step</DropdownMenuItem>}
            <DropdownMenuItem className="text-xs cursor-pointer text-rose-500 focus:text-rose-500" onSelect={onRemove}>Remove from deals</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {error && <p className="text-[11px] text-rose-500">{error}</p>}

      {chase && (
        <Dialog open={nudge} onOpenChange={setNudge}>
          <DialogContent className="sm:max-w-md bg-white dark:bg-[#0c0d0e]">
            <DialogHeader>
              <DialogTitle className="text-[14px] font-medium">Remind {deal.name}</DialogTitle>
              <DialogDescription className="text-xs">{chase.reason}</DialogDescription>
            </DialogHeader>
            <ProposalCard p={chase} api={api} onDone={(d) => { setNudge(false); onProposals(d); }} />
          </DialogContent>
        </Dialog>
      )}
    </li>
  );
}

/** Content: creators you agreed with, from agreed to posted to paid. One row each, one next step. */
export function ContentList({ deals, api, proposals, onChange, onOpenChat, onRemove, onProposals }: {
  deals: Deal[];
  api: Api;
  proposals: Proposal[];
  onChange: (d: Deal) => void;
  onOpenChat: (id: string) => void;
  onRemove: (d: Deal) => void;
  onProposals: (data: { proposals?: Proposal[] }) => void;
}) {
  if (deals.length === 0)
    return (
      <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 px-4 py-12 text-center">
        <p className="text-[13px] text-zinc-900 dark:text-zinc-100">No agreed deals yet</p>
        <p className="text-xs text-zinc-500 mt-1">When a creator agrees in Negotiating, they show up here to track the post and payment.</p>
      </div>
    );
  const order = (d: Deal) => (d.overdue ? 0 : stepOf(d) === 0 ? 1 : stepOf(d) === 1 ? 2 : 3);
  return (
    <ul className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] divide-y divide-zinc-200/70 dark:divide-zinc-800/70">
      {[...deals].sort((a, b) => order(a) - order(b)).map((d) => (
        <Row key={d.id} deal={d} api={api} onChange={onChange} onBack={() => onOpenChat(d.id)} onRemove={() => onRemove(d)}
             chase={proposals.find((p) => p.deal_id === d.id && p.kind === "chase_post")} onProposals={onProposals} />
      ))}
    </ul>
  );
}
