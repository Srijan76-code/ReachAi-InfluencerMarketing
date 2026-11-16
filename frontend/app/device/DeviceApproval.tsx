"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, KeyRound, Loader2, X } from "lucide-react";
import { useApi } from "@/lib/api";
import { btn, btnPrimary, control } from "@/lib/ui";

type Asked = { user_code: string; client_name: string; asked_at: string | null };
type Step = "enter" | "confirm" | "approved" | "denied";

/** Device login (F9.8): an agent or CLI showed a code; the founder confirms once who is asking and approves or denies. */
export default function DeviceApproval({ initialCode }: { initialCode: string }) {
  const api = useApi();
  const [code, setCode] = useState(initialCode);
  const [step, setStep] = useState<Step>("enter");
  const [asked, setAsked] = useState<Asked | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function lookup(value: string) {
    if (!value.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api("/api/device/lookup", { params: { code: value.trim() } });
      setAsked(res.data as Asked);
      setStep("confirm");
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(typeof detail === "string" ? detail : "We couldn't check that code. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(approve: boolean) {
    if (!asked || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/device/decision", { method: "POST", data: { code: asked.user_code, approve } });
      setStep(approve ? "approved" : "denied");
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(typeof detail === "string" ? detail : "That didn't work. Ask your agent for a new code.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initialCode) lookup(initialCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, for a code that came in the link
  }, []);

  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-[#08090a] px-4 pt-24 pb-16">
      <div className="max-w-md mx-auto border border-zinc-200 dark:border-zinc-800 rounded-lg p-5 bg-white dark:bg-[#0c0d0e] space-y-4">
        <div className="flex items-center gap-1.5 text-[14px] font-medium text-zinc-900 dark:text-zinc-100">
          <KeyRound size={14} className="text-zinc-500" /> Connect an agent
        </div>

        {step === "enter" && (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              lookup(code);
            }}
          >
            <p className="text-[13px] text-zinc-600 dark:text-zinc-400">Enter the code your agent showed you.</p>
            <input
              className={`${control} font-mono tracking-widest uppercase`}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="BCDF-GHJK"
              aria-label="Code from your agent"
              autoFocus
              autoComplete="off"
              maxLength={20}
            />
            <button type="submit" className={btnPrimary} disabled={busy || !code.trim()}>
              {busy && <Loader2 size={12} className="animate-spin" />} Continue
            </button>
          </form>
        )}

        {step === "confirm" && asked && (
          <div className="space-y-3">
            <p className="text-[13px] text-zinc-900 dark:text-zinc-100">
              <span className="font-medium">{asked.client_name}</span> wants to connect to your ReachAI account.
            </p>
            <div className="rounded-md bg-zinc-100 dark:bg-[#121314] p-3 space-y-2 text-xs text-zinc-700 dark:text-zinc-300">
              <p>
                <span className="font-medium">It can:</span> find creators, read your results, write drafts, and start a search that uses
                your credits (10 a day at most).
              </p>
              <p>
                <span className="font-medium">It can&apos;t:</span> send messages unless you allow it for a campaign, agree a price, take a
                payment or change your plan.
              </p>
            </div>
            <p className="text-[11px] text-zinc-500">
              Only approve if you started this yourself and the code matches what your agent showed:{" "}
              <span className="font-mono">{asked.user_code}</span>. You can remove the connection any time on the{" "}
              <Link href="/agents" className="underline underline-offset-2">Agents page</Link>.
            </p>
            <div className="flex gap-2">
              <button type="button" className={btnPrimary} onClick={() => decide(true)} disabled={busy}>
                {busy && <Loader2 size={12} className="animate-spin" />} Approve
              </button>
              <button type="button" className={btn} onClick={() => decide(false)} disabled={busy}>
                Deny
              </button>
            </div>
          </div>
        )}

        {step === "approved" && (
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-[13px] text-emerald-600 dark:text-emerald-500">
              <Check size={14} /> Connected.
            </p>
            <p className="text-[13px] text-zinc-600 dark:text-zinc-400">Go back to your agent. It picks up the connection within a few seconds.</p>
          </div>
        )}

        {step === "denied" && (
          <p className="flex items-center gap-1.5 text-[13px] text-zinc-600 dark:text-zinc-400">
            <X size={14} /> Denied. Nothing was connected.
          </p>
        )}

        {error && <p className="text-[11px] text-rose-500">{error}</p>}
      </div>
    </main>
  );
}
