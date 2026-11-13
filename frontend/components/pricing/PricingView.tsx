"use client";

import { useMemo, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import type { Credits } from "@/lib/credits";
import type { Notice } from "@/lib/useCheckout";
import { btn, btnPrimary } from "@/lib/ui";

type PlanId = "free" | "solo" | "pro";

const PLANS: { id: PlanId; item: string | null; name: string; price: number; inr: string | null; credits: number }[] = [
  { id: "free", item: null, name: "Free", price: 0, inr: null, credits: 3 },
  { id: "solo", item: "solo_monthly", name: "Solo", price: 12, inr: "₹499", credits: 25 },
  { id: "pro", item: "pro_monthly", name: "Pro", price: 29, inr: "₹1,299", credits: 80 },
];
const RANK: Record<PlanId, number> = { free: 0, solo: 1, pro: 2 };
const PACKS = [
  { item: "pack_10", credits: 10, price: 8, inr: "₹299" },
  { item: "pack_30", credits: 30, price: 20, inr: "₹799" },
];

const FAQ = [
  ["What's a credit?", "One credit is one YouTube search: up to about 30 creators, ranked for your brief, each with a fair price. X is 3 credits, Instagram 4 and LinkedIn 8."],
  ["What if a search finds too few creators?", "If it finds fewer than 10, the credits come back automatically. They also come back if a search fails."],
  ["What's free?", "Everything after the search: outreach, AI drafts, negotiation, Gmail sending, tracking posts and results, and using ReachAI from your agent."],
  ["Can I cancel?", "Yes, anytime. You keep your plan's credits until the month ends. Pack credits never expire."],
  ["Tax and local prices", "Prices include tax: what you see is what you pay. They are in USD, with fixed prices in rupees in India. The invoice comes from Dodo Payments, our payment provider."],
];

const PLAN_OVER_PACKS_USD = 5;

/** Cheapest way to get `n` searches a month: a plan, plus packs for anything above it. */
export function cheapest(n: number) {
  const packCost = (extra: number) => {
    let best = Infinity;
    for (let k30 = 0; k30 * 30 <= extra + 30; k30++) {
      const rest = Math.max(0, extra - k30 * 30);
      best = Math.min(best, k30 * 20 + Math.ceil(rest / 10) * 8);
    }
    return extra > 0 ? best : 0;
  };
  const options = PLANS.map((p) => {
    const extra = Math.max(0, n - p.credits);
    return { plan: p, extra, cost: p.price + packCost(extra), spare: Math.max(0, p.credits - n) };
  }).sort((a, b) => a.cost - b.cost || RANK[b.plan.id] - RANK[a.plan.id]);
  // A plan that covers everything wins if it's within a few dollars: simpler, and credits roll over.
  const covering = options.find((o) => o.extra === 0 && o.cost - options[0].cost <= PLAN_OVER_PACKS_USD);
  return covering ?? options[0];
}

type Props = {
  credits: Credits | null;
  signedIn: boolean;
  busy?: string | null;
  notice?: Notice;
  onBuy: (item: string) => void;
  onManage?: () => void;
};

const NOTICE_TONE = {
  info: "border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300",
  good: "border-emerald-300/60 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-400",
  bad: "border-rose-300/60 dark:border-rose-500/30 text-rose-600 dark:text-rose-400",
};

export function PricingView({ credits, signedIn, busy = null, notice = null, onBuy, onManage }: Props) {
  const [searches, setSearches] = useState(10);
  const pick = useMemo(() => cheapest(searches), [searches]);
  const current: PlanId = (credits?.plan as PlanId) ?? "free";
  const canBuy = !signedIn || credits?.payments !== false;

  const pickText =
    pick.extra > 0
      ? `${pick.plan.name}${pick.plan.price ? ` ($${pick.plan.price}/mo)` : ""} plus packs for the other ${pick.extra}: about $${pick.cost} a month.`
      : pick.plan.id === "free"
        ? "Free covers it."
        : `${pick.plan.name} ($${pick.plan.price}/mo) covers it${pick.spare ? `, with ${pick.spare} to spare` : ""}.`;

  const planButton = (p: (typeof PLANS)[number]) => {
    if (signedIn && current === p.id) {
      return (
        <p className="flex items-center justify-center gap-1 h-[30px] text-xs text-zinc-500">
          <Check className="w-3 h-3" /> Your plan
        </p>
      );
    }
    if (p.id === "free") {
      return signedIn ? (
        <p className="flex items-center justify-center h-[30px] text-[11px] text-zinc-500">Cancel anytime in Manage plan</p>
      ) : (
        <button type="button" onClick={() => onBuy("free")} className={`${btn} w-full`}>
          Start free
        </button>
      );
    }
    const up = !signedIn || RANK[p.id] > RANK[current];
    return (
      <button
        type="button"
        onClick={() => p.item && onBuy(p.item)}
        disabled={Boolean(busy) || !canBuy}
        className={`${p.id === pick.plan.id && up ? btnPrimary : btn} w-full`}
      >
        {busy === p.item ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
        {!canBuy ? "Coming soon" : !signedIn || current === "free" ? `Get ${p.name}` : up ? `Upgrade to ${p.name}` : `Switch to ${p.name}`}
      </button>
    );
  };

  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 pt-24 pb-20 space-y-12">
      <header className="text-center space-y-2">
        <h1 className="text-2xl font-medium tracking-tight text-zinc-900 dark:text-zinc-100">Pay only to find creators</h1>
        <p className="text-sm text-zinc-500">Outreach, AI drafts, negotiation, tracking and agents are free on every plan.</p>
      </header>

      {notice && (
        <p role="status" className={`max-w-xl mx-auto rounded-lg border px-4 py-2.5 text-xs flex items-center justify-center gap-2 ${NOTICE_TONE[notice.tone]}`}>
          {notice.tone === "info" && <Loader2 className="w-3 h-3 animate-spin shrink-0" />}
          {notice.text}
        </p>
      )}

      <section className="max-w-xl mx-auto space-y-2">
        <div className="flex items-baseline justify-between text-xs">
          <label htmlFor="searches" className="text-zinc-600 dark:text-zinc-400">
            Creator searches a month
          </label>
          <span className="font-mono tabular-nums text-zinc-900 dark:text-zinc-100">{searches}</span>
        </div>
        <input
          id="searches"
          type="range"
          min={1}
          max={150}
          value={searches}
          onChange={(e) => setSearches(Number(e.target.value))}
          className="w-full h-1.5 appearance-none rounded-full bg-zinc-200 dark:bg-zinc-800 cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:size-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-zinc-900 dark:[&::-webkit-slider-thumb]:bg-zinc-200 [&::-webkit-slider-thumb]:shadow [&::-moz-range-thumb]:size-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-zinc-900 dark:[&::-moz-range-thumb]:bg-zinc-200"
        />
        <p className="text-xs text-zinc-500 text-center">{pickText}</p>
      </section>

      <section className="grid sm:grid-cols-3 gap-3">
        {PLANS.map((p) => {
          const best = p.id === pick.plan.id;
          return (
            <div
              key={p.id}
              className={`rounded-lg border p-5 flex flex-col gap-4 transition-colors ${
                best ? "border-zinc-900 dark:border-zinc-300" : "border-zinc-200 dark:border-zinc-800"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">{p.name}</span>
                {best && <span className="text-[11px] text-zinc-500">Best for {searches}/mo</span>}
              </div>
              <div>
                <span className="text-3xl font-medium tracking-tight text-zinc-900 dark:text-zinc-100">${p.price}</span>
                <span className="text-xs text-zinc-500">{p.price ? " /month" : ""}</span>
                {p.inr && <p className="text-[11px] text-zinc-500 mt-0.5">{p.inr}/month in India</p>}
              </div>
              <ul className="space-y-1.5 text-xs text-zinc-600 dark:text-zinc-400 flex-1">
                <li>
                  <span className="text-zinc-900 dark:text-zinc-100">{p.credits} searches</span> a month
                </li>
                <li>{p.id === "free" ? "Plus 5 welcome credits" : "Unused credits roll over a month"}</li>
                <li>Everything else free</li>
              </ul>
              {planButton(p)}
            </div>
          );
        })}
      </section>

      <section id="packs" className="rounded-lg border border-zinc-200 dark:border-zinc-800 px-4 sm:px-5 py-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[13px] text-zinc-900 dark:text-zinc-100">Need more searches?</p>
          <p className="text-[11px] text-zinc-500">Credit packs never expire and work on any plan.</p>
        </div>
        <div className="flex gap-2">
          {PACKS.map((p) => (
            <button
              key={p.item}
              type="button"
              onClick={() => onBuy(p.item)}
              disabled={Boolean(busy) || !canBuy}
              title={`${p.inr} in India`}
              className={btn}
            >
              {busy === p.item ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
              {p.credits} credits · ${p.price}
            </button>
          ))}
        </div>
      </section>

      <section className="max-w-2xl mx-auto space-y-3">
        <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100 text-center">Questions</h2>
        <div className="divide-y divide-zinc-200 dark:divide-zinc-800 border-y border-zinc-200 dark:border-zinc-800">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group">
              <summary className="cursor-pointer list-none flex items-center justify-between py-3 text-[13px] text-zinc-900 dark:text-zinc-100">
                {q}
                <span className="text-zinc-400 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pb-3 text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">{a}</p>
            </details>
          ))}
        </div>
        {signedIn && credits?.can_manage && onManage && (
          <p className="text-center">
            <button type="button" onClick={onManage} className="text-xs text-zinc-500 underline underline-offset-2">
              Manage plan, invoices and card
            </button>
          </p>
        )}
      </section>
    </main>
  );
}
