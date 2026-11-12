"use client";

import NumberFlow from "@number-flow/react";
import { Check } from "lucide-react";
import { type Credits, plural, resetLabel } from "@/lib/credits";
import { btn } from "@/lib/ui";

export type Entry = { delta: number; bucket: string; reason: string; note: string | null; at: string | null };

const PLANS = [
  { id: "free", name: "Free", price: "$0", inr: null, credits: 3, extra: "All features" },
  { id: "solo", name: "Solo", price: "$12", inr: "₹499", credits: 25, extra: "Unused credits roll over a month" },
  { id: "pro", name: "Pro", price: "$29", inr: "₹1,299", credits: 80, extra: "Unused credits roll over a month" },
];

const PLATFORMS = [
  { id: "youtube", name: "YouTube", credits: 1 },
  { id: "x", name: "X", credits: 3 },
  { id: "instagram", name: "Instagram", credits: 4 },
  { id: "linkedin", name: "LinkedIn", credits: 8 },
];

const BUCKETS: Record<string, string> = { monthly: "This month", rollover: "From last month", bonus: "Bonus", pack: "Packs" };

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

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";

/** The billing page's content. Data comes from the page (or a test harness). */
export function BillingView({ credits, history }: { credits: Credits | null; history: Entry[] | null }) {
  const live = credits?.search_credits ?? { youtube: 1 };

  return (
    <main className="max-w-3xl mx-auto px-6 pt-24 pb-16 space-y-10">
      <section className="space-y-1">
        <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100">Billing</h1>
        <p className="text-xs text-zinc-500">Only creator searches use credits. Outreach, drafts, negotiation, tracking and agents are free.</p>
      </section>

      <section className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] p-5 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="text-[11px] text-zinc-500">Credits</p>
          <div className="text-3xl font-mono tabular-nums text-zinc-900 dark:text-zinc-100">
            {credits ? <NumberFlow value={credits.balance} /> : "—"}
          </div>
          {credits && (
            <p className="text-xs text-zinc-500 mt-1">
              {PLANS.find((p) => p.id === credits.plan)?.name ?? credits.plan} plan · {plural(credits.monthly_credits)} a month · resets{" "}
              {resetLabel(credits.resets_at)}
              {credits.held ? ` · ${plural(credits.held)} held for a running search` : ""}
            </p>
          )}
        </div>
        {credits && (
          <dl className="flex gap-5 text-xs">
            {Object.entries(credits.buckets)
              .filter(([, n]) => n > 0)
              .map(([b, n]) => (
                <div key={b}>
                  <dt className="text-[11px] text-zinc-500">{BUCKETS[b] ?? b}</dt>
                  <dd className="font-mono tabular-nums text-zinc-900 dark:text-zinc-100">{n}</dd>
                </div>
              ))}
          </dl>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">Cost per search</h2>
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 divide-y divide-zinc-200 dark:divide-zinc-800">
          {PLATFORMS.map((p) => (
            <div key={p.id} className="flex items-center justify-between px-4 h-10 text-[13px]">
              <span className="text-zinc-900 dark:text-zinc-100">{p.name}</span>
              {p.id in live ? (
                <span className="text-xs text-zinc-700 dark:text-zinc-300">{plural(live[p.id])}</span>
              ) : (
                <span className="text-xs text-zinc-500">{plural(p.credits)} · coming soon</span>
              )}
            </div>
          ))}
        </div>
        <p className="text-[11px] text-zinc-500">
          Up to about 30 ranked creators per search. If a search finds fewer than 10, its credits come back.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">Plans</h2>
        <div className="grid sm:grid-cols-3 gap-3">
          {PLANS.map((p) => {
            const current = credits?.plan === p.id;
            return (
              <div
                key={p.id}
                className={`rounded-lg border p-4 space-y-3 ${
                  current ? "border-zinc-400 dark:border-zinc-600" : "border-zinc-200 dark:border-zinc-800"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">{p.name}</span>
                  <span className="text-[13px] text-zinc-900 dark:text-zinc-100">
                    {p.price}
                    <span className="text-[11px] text-zinc-500">{p.id === "free" ? "" : "/mo"}</span>
                  </span>
                </div>
                <ul className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
                  <li>{plural(p.credits)} a month</li>
                  <li>{p.extra}</li>
                  {p.inr && <li className="text-zinc-500">{p.inr}/mo in India</li>}
                </ul>
                {current ? (
                  <p className="flex items-center gap-1 text-xs text-zinc-500">
                    <Check className="w-3 h-3" /> Current plan
                  </p>
                ) : (
                  <button type="button" disabled className={`${btn} w-full`}>
                    {p.id === "free" ? "Free" : "Coming soon"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
        <p className="text-[11px] text-zinc-500">Credit packs (10 for $8, 30 for $20, never expire) are coming soon too.</p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">History</h2>
        {history === null ? (
          <p className="text-xs text-zinc-500">Loading…</p>
        ) : history.length === 0 ? (
          <p className="text-xs text-zinc-500">Nothing yet.</p>
        ) : (
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 divide-y divide-zinc-200 dark:divide-zinc-800">
            {history.map((e, i) => (
              <div key={i} className="flex items-center gap-3 px-4 h-10 text-[13px]">
                <span className="w-14 text-[11px] text-zinc-500 shrink-0">{when(e.at)}</span>
                <span className="flex-1 min-w-0 truncate text-zinc-800 dark:text-zinc-200">
                  {REASONS[e.reason] ?? e.reason}
                  {e.note && e.reason !== "grant_welcome" ? <span className="text-zinc-500"> · {e.note}</span> : null}
                </span>
                <span
                  className={`font-mono tabular-nums text-xs ${
                    e.delta > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-600 dark:text-zinc-400"
                  }`}
                >
                  {e.delta > 0 ? `+${e.delta}` : e.delta}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
