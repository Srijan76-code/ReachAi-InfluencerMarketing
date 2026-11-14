"use client";

import { useEffect, useState } from "react";
import { Check, ChevronDown, Sparkles } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
type State = { autopilot: boolean; review_first: boolean };

/** Autopilot for this campaign: ReachAI sends first emails, follow-ups and replies by itself, and stops for you
 * when a creator accepts, declines or asks something only you can answer. Needs Gmail. */
export function Autopilot({ campaignId, api, gmailReady, onChange }: { campaignId: string; api: Api; gmailReady: boolean; onChange?: () => void }) {
  const [s, setS] = useState<State | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api(`/api/campaigns/${campaignId}/autopilot`).then((r) => setS(r.data as State)).catch(() => setS(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [campaignId]);

  const save = async (next: State) => {
    const prev = s;
    setS(next);
    setBusy(true);
    try {
      await api(`/api/campaigns/${campaignId}/autopilot`, { method: "PUT", data: next });
      onChange?.();
    } catch {
      setS(prev);
    } finally {
      setBusy(false);
    }
  };

  if (!s) return null;
  const on = s.autopilot && gmailReady;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" disabled={busy} aria-label={`Autopilot ${on ? "on" : "off"}. Change`}
          className={`inline-flex items-center gap-1.5 h-[30px] px-2.5 text-xs font-medium rounded-md border transition-colors disabled:opacity-60
            ${on ? "border-violet-300/70 dark:border-violet-500/30 text-violet-700 dark:text-violet-300 bg-violet-50/60 dark:bg-violet-500/5"
              : "border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}>
          <span className="relative flex w-1.5 h-1.5">
            {on && <span className="absolute inset-0 rounded-full bg-violet-500 animate-ping opacity-60 motion-reduce:animate-none" />}
            <span className={`relative w-1.5 h-1.5 rounded-full ${on ? "bg-violet-500" : "bg-zinc-300 dark:bg-zinc-600"}`} />
          </span>
          Autopilot {on ? "on" : "off"} <ChevronDown size={11} className="opacity-60" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
        <DropdownMenuLabel className="text-[11px] font-normal text-zinc-500 leading-relaxed">
          {gmailReady ? "Sends first emails, follow-ups and replies from your Gmail, spaced out. Stops for you when a creator accepts, declines or asks something."
            : "Connect Gmail to let ReachAI send for you."}
        </DropdownMenuLabel>
        <DropdownMenuItem disabled={!gmailReady} className="text-xs cursor-pointer flex items-start gap-2" onSelect={() => save({ ...s, autopilot: !s.autopilot })}>
          <Sparkles size={13} className="mt-0.5 shrink-0 text-violet-500" />
          <span className="flex-1">{s.autopilot ? "Turn autopilot off" : "Turn autopilot on"}</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={!s.autopilot} className="text-xs cursor-pointer flex items-start gap-2" onSelect={() => save({ ...s, review_first: !s.review_first })}>
          <span className="w-[13px] mt-0.5 shrink-0">{s.review_first && <Check size={13} />}</span>
          <span className="flex-1">
            <span className="block">Let me check first emails</span>
            <span className="block text-[10px] text-zinc-500">They wait in each chat until you send them</span>
          </span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
