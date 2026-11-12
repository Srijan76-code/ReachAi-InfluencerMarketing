"use client";

import NumberFlow from "@number-flow/react";
import { Check, Loader2 } from "lucide-react";
import { type Credits, plural, resetLabel } from "@/lib/credits";
import { btn, btnPrimary } from "@/lib/ui";

export type Entry = { delta: number; bucket: string; reason: string; note: string | null; at: string | null };
export type Notice = { tone: "info" | "good" | "bad"; text: string } | null;

const PLANS = [
  { id: "free", item: null, name: "Free", price: "$0", inr: null, credits: 3, extra: "All features" },
  { id: "solo", item: "solo_monthly", name: "Solo", price: "$12", inr: "₹499", credits: 25, extra: "Unused credits roll over a month" },
  { id: "pro", item: "pro_monthly", name: "Pro", price: "$29", inr: "₹1,299", credits: 80, extra: "Unused credits roll over a month" },
];
const RANK: Record<string, number> = { free: 0, solo: 1, pro: 2 };

const PACKS = [
  { item: "pack_10", credits: 10, price: "$8", inr: "₹299" },
  { item: "pack_30", credits: 30, price: "$20", inr: "₹799" },
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

const NOTICE_TONE = {
  info: "border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300",
  good: "border-emerald-300/60 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-400",
  bad: "border-rose-300/60 dark:border-rose-500/30 text-rose-600 dark:text-rose-400",
};

type Props = {
  credits: Credits | null;
  history: Entry[] | null;
  busy?: string | null;
  notice?: Notice;
  onBuy?: (item: string) => void;
  onManage?: () => void;
};

/** The billing page's content. Data and actions come from the page (or a test harness). */
export function BillingView({ credits, history, busy = null, notice = null, onBuy, onManage }: Props) {
  const live = credits?.search_credits ?? { youtube: 1 };
  const canBuy = Boolean(credits?.payments && onBuy);
  const current = credits?.plan ?? "free";
  const paid = current !== "free";

  const planButton = (p: (typeof PLANS)[number]) => {
    if (current === p.id) {
      return (
        <p className="flex items-center gap-1 h-[30px] text-xs text-zinc-500">
          <Check className="w-3 h-3" /> Current plan
        </p>
      );
    }
    if (p.id === "free") {
      return paid ? <p className="h-[30px] text-[11px] text-zinc-500 flex items-center">Cancel in Manage plan</p> : null;
    }
    if (!canBuy) {
      return (
        <button type="button" disabled className={`${btn} w-full`}>
          Coming soon
        </button>
      );
    }
    const up = RANK[p.id] > RANK[current];
    return (
      <button
        type="button"
        onClick={() => p.item && onBuy?.(p.item)}
        disabled={Boolean(busy)}
        className={`${up ? btnPrimary : btn} w-full`}
      >
        {busy === p.item ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
        {up ? (paid ? `Upgrade to ${p.name}` : `Get ${p.name}`) : `Switch to ${p.name}`}
      </button>
    );
  };

  return (
    <main className="max-w-3xl mx-auto px-6 pt-24 pb-16 space-y-10">
      <section className="space-y-1">
        <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100">Billing</h1>
        <p className="text-xs text-zinc-500">Only creator searches use credits. Outreach, drafts, negotiation, tracking and agents are free.</p>
      </section>

      {notice && (
        <p role="status" className={`rounded-lg border px-4 py-2.5 text-xs flex items-center gap-2 ${NOTICE_TONE[notice.tone]}`}>
          {notice.tone === "info" && <Loader2 className="w-3 h-3 animate-spin shrink-0" />}
          {notice.text}
        </p>
      )}

      <section className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] p-5 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="text-[11px] text-zinc-500">Credits</p>
          <div className="text-3xl font-mono tabular-nums text-zinc-900 dark:text-zinc-100">
            {credits ? <NumberFlow value={credits.balance} /> : "—"}
          </div>
          {credits && (
            <p className="text-xs text-zinc-500 mt-1">
              {PLANS.find((p) => p.id === credits.plan)?.name ?? credits.plan} plan · {plural(credits.monthly_credits)} a month ·{" "}
              {credits.cancel_at_period_end ? "ends" : paid ? "renews" : "resets"} {resetLabel(credits.resets_at)}
              {credits.held ? ` · ${plural(credits.held)} held for a running search` : ""}
            </p>
          )}
          {credits?.status === "past_due" && (
            <p className="text-xs text-rose-600 dark:text-rose-400 mt-1">The last payment didn&apos;t go through. Update your card in Manage plan.</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-3">
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
          {credits?.can_manage && onManage && (
            <button type="button" onClick={onManage} disabled={busy === "portal"} className={btn}>
              {busy === "portal" ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
              Manage plan
            </button>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">Plans</h2>
        <div className="grid sm:grid-cols-3 gap-3">
          {PLANS.map((p) => (
            <div
              key={p.id}
              className={`rounded-lg border p-4 flex flex-col gap-3 ${
                current === p.id ? "border-zinc-400 dark:border-zinc-600" : "border-zinc-200 dark:border-zinc-800"
              }`}
            >
              <div className="flex items-baseline justify-between">
                <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">{p.name}</span>
                <span className="text-[13px] text-zinc-900 dark:text-zinc-100">
                  {p.price}
                  <span className="text-[11px] text-zinc-500">{p.id === "free" ? "" : "/mo"}</span>
                </span>
              </div>
              <ul className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400 flex-1">
                <li>{plural(p.credits)} a month</li>
                <li>{p.extra}</li>
                {p.inr && <li className="text-zinc-500">{p.inr}/mo in India</li>}
              </ul>
              {planButton(p)}
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">Credit packs</h2>
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 divide-y divide-zinc-200 dark:divide-zinc-800">
          {PACKS.map((p) => (
            <div key={p.item} className="flex items-center justify-between gap-3 px-4 h-12 text-[13px]">
              <span className="text-zinc-900 dark:text-zinc-100">{plural(p.credits)}</span>
              <span className="flex items-center gap-3">
                <span className="text-xs text-zinc-500 hidden sm:inline">{p.inr} in India</span>
                {canBuy ? (
                  <button type="button" onClick={() => onBuy?.(p.item)} disabled={Boolean(busy)} className={btn}>
                    {busy === p.item ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                    Buy · {p.price}
                  </button>
                ) : (
                  <span className="text-xs text-zinc-500">{p.price} · coming soon</span>
                )}
              </span>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-zinc-500">Pack credits never expire and are used after your monthly credits. Tax is added at checkout where it applies.</p>
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
                  {e.note && !["grant_welcome", "grant_pack"].includes(e.reason) ? <span className="text-zinc-500"> · {e.note}</span> : null}
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
