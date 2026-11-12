"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import NumberFlow from "@number-flow/react";
import { Loader2 } from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useApi } from "@/lib/api";
import { type Credits, plural, resetLabel, useCredits } from "@/lib/credits";
import { usagePanel, useUsagePanel } from "@/lib/usage";
import { useCheckout } from "@/lib/useCheckout";
import { btn, btnPrimary } from "@/lib/ui";

type Entry = { delta: number; bucket: string; reason: string; note: string | null; at: string | null };

const REASONS: Record<string, string> = {
  grant_plan: "Monthly credits",
  grant_welcome: "Welcome credits",
  grant_pack: "Credit pack",
  grant_referral: "Referral",
  rollover: "Carried over",
  expire: "Expired",
  reserve: "Creator search",
  release: "Returned",
  refund: "Returned",
  adjust: "Adjustment",
};
const BUCKETS: Record<string, string> = { monthly: "This month", rollover: "Carried over", bonus: "Bonus", pack: "Packs" };
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "");
const title = (plan: string) => plan[0].toUpperCase() + plan.slice(1);

/** Your credits, plan and history, in a side panel opened from the avatar menu. */
export function UsageSheet() {
  const open = useUsagePanel();
  const credits = useCredits();
  const api = useApi();
  const [history, setHistory] = useState<Entry[] | null>(null);
  const load = useCallback(() => {
    api("/api/billing/history")
      .then((r) => setHistory((r.data as { entries: Entry[] }).entries))
      .catch(() => setHistory([]));
  }, [api]);
  const { manage, busy, notice } = useCheckout(credits, load);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  return (
    <Sheet open={open} onOpenChange={(o) => (o ? usagePanel.open() : usagePanel.close())}>
      <SheetContent className="w-full sm:max-w-sm p-0 gap-0 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
        <SheetHeader className="p-5 bg-zinc-50 dark:bg-[#08090a] border-b border-zinc-200 dark:border-zinc-800">
          <SheetTitle className="text-[14px] font-medium">Billing and usage</SheetTitle>
          <SheetDescription className="text-xs">Only creator searches use credits.</SheetDescription>
        </SheetHeader>
        <div className="p-5 space-y-6 overflow-y-auto">
          <Summary credits={credits} />
          <div className="flex gap-2">
            {credits?.can_manage ? (
              <button type="button" onClick={manage} disabled={busy === "portal"} className={`${btn} flex-1`}>
                {busy === "portal" ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                Manage plan
              </button>
            ) : null}
            <Link href="/pricing" onClick={() => usagePanel.close()} className={`${credits?.can_manage ? btn : btnPrimary} flex-1`}>
              {credits?.plan === "free" ? "Upgrade or buy credits" : "Buy more credits"}
            </Link>
          </div>
          {notice && <p className="text-xs text-rose-600 dark:text-rose-400">{notice.text}</p>}
          <section className="space-y-2">
            <h3 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">History</h3>
            {history === null ? (
              <p className="text-xs text-zinc-500">Loading…</p>
            ) : history.length === 0 ? (
              <p className="text-xs text-zinc-500">Nothing yet.</p>
            ) : (
              <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {history.map((e, i) => (
                  <li key={i} className="flex items-center gap-3 py-2 text-xs">
                    <span className="w-12 text-[11px] text-zinc-500 shrink-0">{when(e.at)}</span>
                    <span className="flex-1 min-w-0 truncate text-zinc-800 dark:text-zinc-200">
                      {REASONS[e.reason] ?? e.reason}
                      {e.note && !["grant_welcome", "grant_pack"].includes(e.reason) ? (
                        <span className="text-zinc-500"> · {e.note}</span>
                      ) : null}
                    </span>
                    <span className={`font-mono tabular-nums ${e.delta > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-500"}`}>
                      {e.delta > 0 ? `+${e.delta}` : e.delta}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Summary({ credits }: { credits: Credits | null }) {
  if (!credits) return <p className="text-xs text-zinc-500">Loading…</p>;
  const paid = credits.plan !== "free";
  return (
    <section className="space-y-3">
      <div>
        <div className="text-3xl font-mono tabular-nums text-zinc-900 dark:text-zinc-100">
          <NumberFlow value={credits.balance} />
        </div>
        <p className="text-xs text-zinc-500 mt-0.5">
          {title(credits.plan)} plan · {plural(credits.monthly_credits)} a month · {credits.cancel_at_period_end ? "ends" : paid ? "renews" : "resets"}{" "}
          {resetLabel(credits.resets_at)}
        </p>
        {credits.held ? <p className="text-[11px] text-zinc-500">{plural(credits.held)} held for a running search</p> : null}
        {credits.status === "past_due" && (
          <p className="text-[11px] text-rose-600 dark:text-rose-400 mt-1">The last payment didn&apos;t go through. Update your card in Manage plan.</p>
        )}
      </div>
      <dl className="grid grid-cols-4 gap-2">
        {Object.entries(credits.buckets).map(([b, n]) => (
          <div key={b} className="rounded-md bg-zinc-100 dark:bg-[#121314] px-2 py-1.5">
            <dt className="text-[10px] text-zinc-500 truncate">{BUCKETS[b] ?? b}</dt>
            <dd className="text-xs font-mono tabular-nums text-zinc-900 dark:text-zinc-100">{n}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
