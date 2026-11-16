"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, Loader2, ShieldCheck, X } from "lucide-react";
import { useApi } from "@/lib/api";
import { btn, btnPrimary, control } from "@/lib/ui";
import { Segmented } from "@/components/ui/segmented";

type Asked = {
  user_code: string;
  label: string;
  what: string;
  campaign_name: string | null;
  client_name: string;
  mode: "ask" | "unattended";
  per_day: number | null;
  requested_days: number;
  max_days: number;
  per_day_range: [number, number] | null;
  can_unattended: boolean;
};
type Step = "enter" | "confirm" | "approved" | "denied";

/** Allow your agent (F9.8, 8b): the founder reads what an agent asked for in plain words, can make it shorter or stricter,
 * and approves once. An agent can't do this for itself: it needs the website sign-in. */
export default function GrantApproval({ initialCode }: { initialCode: string }) {
  const api = useApi();
  const [code, setCode] = useState(initialCode);
  const [step, setStep] = useState<Step>("enter");
  const [asked, setAsked] = useState<Asked | null>(null);
  const [days, setDays] = useState(7);
  const [perDay, setPerDay] = useState<number | null>(null);
  const [mode, setMode] = useState<"ask" | "unattended">("ask");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown, fallback: string) => {
    const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    setError(typeof detail === "string" ? detail : fallback);
  };

  async function lookup(value: string) {
    if (!value.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const a = (await api("/api/grants/lookup", { params: { code: value.trim() } })).data as Asked;
      setAsked(a);
      setDays(a.requested_days);
      setPerDay(a.per_day);
      setMode(a.mode);
      setStep("confirm");
    } catch (e) {
      fail(e, "We couldn't check that code. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(approve: boolean) {
    if (!asked || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/grants/decision", {
        method: "POST",
        data: { code: asked.user_code, approve, ...(approve ? { days, per_day: perDay ?? undefined, mode } : {}) },
      });
      setStep(approve ? "approved" : "denied");
    } catch (e) {
      fail(e, "That didn't work. Ask your agent to ask again.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initialCode) lookup(initialCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, for a code that came in the link
  }, []);

  const sends = !!asked?.per_day_range;
  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-[#08090a] px-4 pt-24 pb-16">
      <div className="max-w-md mx-auto border border-zinc-200 dark:border-zinc-800 rounded-lg p-5 bg-white dark:bg-[#0c0d0e] space-y-4">
        <div className="flex items-center gap-1.5 text-[14px] font-medium text-zinc-900 dark:text-zinc-100">
          <ShieldCheck size={14} className="text-zinc-500" /> Allow your agent
        </div>

        {step === "enter" && (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); lookup(code); }}>
            <p className="text-[13px] text-zinc-600 dark:text-zinc-400">Enter the code your agent showed you.</p>
            <input className={`${control} font-mono tracking-widest uppercase`} value={code} onChange={(e) => setCode(e.target.value)}
              placeholder="BCDF-GHJK" aria-label="Code from your agent" autoFocus autoComplete="off" maxLength={20} />
            <button type="submit" className={btnPrimary} disabled={busy || !code.trim()}>
              {busy && <Loader2 size={12} className="animate-spin" />} Continue
            </button>
          </form>
        )}

        {step === "confirm" && asked && (
          <div className="space-y-3">
            <p className="text-[13px] text-zinc-900 dark:text-zinc-100">
              <span className="font-medium">{asked.client_name}</span> asks to <span className="font-medium">{asked.label.toLowerCase()}</span>
              {asked.campaign_name ? <> in <span className="font-medium">{asked.campaign_name}</span></> : null}.
            </p>
            <div className="rounded-md bg-zinc-100 dark:bg-[#121314] p-3 text-xs text-zinc-700 dark:text-zinc-300">{asked.what}</div>

            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-[11px] text-zinc-500">For how many days</span>
                <input className={control} type="number" min={1} max={asked.requested_days} value={days}
                  onChange={(e) => setDays(Math.max(1, Math.min(asked.requested_days, Number(e.target.value) || 1)))} />
              </label>
              {sends && asked.per_day_range && (
                <label className="flex flex-col gap-1">
                  <span className="text-[11px] text-zinc-500">Messages a day, at most</span>
                  <input className={control} type="number" min={1} max={asked.per_day ?? asked.per_day_range[1]} value={perDay ?? ""}
                    onChange={(e) => setPerDay(Math.max(1, Math.min(asked.per_day ?? asked.per_day_range![1], Number(e.target.value) || 1)))} />
                </label>
              )}
            </div>

            {asked.can_unattended && asked.mode === "unattended" && (
              <div className="space-y-1">
                <span className="text-[11px] text-zinc-500">How it sends</span>
                <Segmented size="sm" label="How it sends" value={mode} onChange={setMode}
                  options={[{ value: "ask", label: "I say yes each time" }, { value: "unattended", label: "By itself, within these limits" }]} />
              </div>
            )}
            {sends && (
              <p className="text-[11px] text-zinc-500">
                Messages go from your Gmail, ReachAI checks each one first, and you get an email for every message. It never agrees a
                price, closes a deal or takes a payment.
              </p>
            )}
            <p className="text-[11px] text-zinc-500">
              Only approve if you asked for this yourself and the code is <span className="font-mono">{asked.user_code}</span>. You can
              remove it any time on the <Link href="/agents" className="underline underline-offset-2">Agents page</Link>.
            </p>
            <div className="flex gap-2">
              <button type="button" className={btnPrimary} onClick={() => decide(true)} disabled={busy}>
                {busy && <Loader2 size={12} className="animate-spin" />} Approve
              </button>
              <button type="button" className={btn} onClick={() => decide(false)} disabled={busy}>Deny</button>
            </div>
          </div>
        )}

        {step === "approved" && (
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-[13px] text-emerald-600 dark:text-emerald-500"><Check size={14} /> Allowed.</p>
            <p className="text-[13px] text-zinc-600 dark:text-zinc-400">Go back to your agent. It can use this now, until it ends or you remove it.</p>
          </div>
        )}
        {step === "denied" && (
          <p className="flex items-center gap-1.5 text-[13px] text-zinc-600 dark:text-zinc-400"><X size={14} /> Denied. Nothing changed.</p>
        )}
        {error && <p className="text-[11px] text-rose-500">{error}</p>}
      </div>
    </main>
  );
}
