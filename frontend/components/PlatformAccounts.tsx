"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { ArrowUpRight, Loader2 } from "lucide-react";
import { RiInstagramFill, RiLinkedinBoxFill, RiTwitterXFill, RiYoutubeFill } from "@remixicon/react";
import type { Account } from "@/data/influencerList";
import { compact } from "@/lib/posts";
import { btn } from "@/lib/ui";
import { useApi } from "@/lib/api";
import { StatStrip, StatTile } from "@/components/ui/stat";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export const PLATFORM_ICON = { youtube: RiYoutubeFill, x: RiTwitterXFill, instagram: RiInstagramFill, linkedin: RiLinkedinBoxFill } as const;
export const PLATFORM_NAME: Record<string, string> = { youtube: "YouTube", x: "X", instagram: "Instagram", linkedin: "LinkedIn" };

function Icon({ platform, size = 13, className = "" }: { platform: string; size?: number; className?: string }) {
  const C = PLATFORM_ICON[platform as keyof typeof PLATFORM_ICON];
  return C ? <C size={size} aria-hidden className={className} /> : null;
}

const tone = (a: Account) =>
  a.status === "main" ? "text-zinc-700 dark:text-zinc-200"
    : a.status === "linked" ? "text-zinc-400 dark:text-zinc-500"
    : "text-zinc-300 dark:text-zinc-700"; // suggested or not measured yet

/** The results row: one small icon per platform the person is on. Hover for the total audience. */
export function PlatformStack({ accounts, reachTotal }: { accounts?: Account[]; reachTotal?: number }) {
  if (!accounts || accounts.length < 2) return null;
  const linked = accounts.filter((a) => a.status === "main" || a.status === "linked").length;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="flex items-center gap-0.5 flex-shrink-0" aria-label={`On ${accounts.length} platforms`}>
          {accounts.map((a) => <Icon key={a.platform} platform={a.platform} size={12} className={tone(a)} />)}
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="text-xs">
        {reachTotal ? <><span className="font-mono">{compact(reachTotal)}</span> followers across {linked} platform{linked === 1 ? "" : "s"}</> : `On ${accounts.length} platforms`}
      </TooltipContent>
    </Tooltip>
  );
}

/** The creator panel: switch between the person's platforms. The main one is the rest of the panel; the others
 * show their own measured numbers, a "probably the same person" note, or a button to measure them. */
export function PlatformSwitcher({ accounts: initial, campaignId, leadId, readOnly }: {
  accounts?: Account[]; campaignId?: string; leadId: string; readOnly?: boolean;
}) {
  const api = useApi();
  const [accounts, setAccounts] = useState(initial ?? []);
  const [on, setOn] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (accounts.length < 2) return null;
  const pick = accounts.find((a) => a.platform === on && !a.main) ?? null;

  const measure = async (platform: string) => {
    if (!campaignId) return;
    setBusy(true);
    setError(null);
    try {
      const r = (await api(`/api/campaigns/${campaignId}/leads/${encodeURIComponent(leadId)}/accounts/measure`, { method: "POST", data: { platform } })).data as { accounts: Account[] };
      setAccounts(r.accounts);
      if (!r.accounts.some((a) => a.platform === platform && a.measured)) setError("That account isn't the same person, so it was left out.");
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Couldn't measure it. Try again");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div role="tablist" aria-label="Platforms" className="flex items-center gap-1">
        {accounts.map((a) => {
          const active = (on ?? accounts[0].platform) === a.platform;
          return (
            <button key={a.platform} type="button" role="tab" aria-selected={active}
              onClick={() => { setOn(a.platform); setError(null); }}
              className={`relative h-[30px] px-2.5 rounded-md flex items-center gap-1.5 text-xs transition-colors ${active ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"} ${a.status === "suggested" || !a.measured ? "border border-dashed border-zinc-300 dark:border-zinc-700" : ""}`}>
              {active && <motion.span layoutId="platform-pill" className="absolute inset-0 rounded-md bg-white dark:bg-[#121314] shadow-sm border border-zinc-200 dark:border-zinc-800" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
              <Icon platform={a.platform} className="relative" />
              <span className="relative font-mono tabular-nums">{a.measured ? compact(a.followers) : "?"}</span>
            </button>
          );
        })}
      </div>

      {pick && (
        <motion.div key={pick.platform} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-2.5">
          {pick.measured ? (
            <>
              <StatStrip cols={4}>
                <StatTile label="Followers" value={<span className="font-mono">{compact(pick.followers)}</span>} />
                <StatTile label="Typical views" value={<span className="font-mono">{pick.avg_views != null ? compact(pick.avg_views) : "—"}</span>}
                  help={pick.platform === "linkedin" ? "LinkedIn doesn't show views." : "The middle of their recent posts' views."} />
                <StatTile label="Engagement" value={<span className="font-mono">{pick.engagement_rate != null ? `${pick.engagement_rate}%` : "—"}</span>} />
                <StatTile label="Fair price" value={pick.valuation != null ? <span className="font-mono">${Math.round(pick.valuation)}</span> : <span className="text-zinc-400 font-normal">No price yet</span>} />
              </StatStrip>
              <div className="flex items-center justify-between text-[11px] text-zinc-500">
                <span>{pick.status === "suggested" ? "Probably them: same name, checked by AI, no link yet" : pick.posts_per_week != null ? <>Posts <span className="font-mono">{pick.posts_per_week}</span> a week</> : null}</span>
                {pick.url && <a href={pick.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-0.5 hover:text-zinc-900 dark:hover:text-zinc-100">Open <ArrowUpRight size={12} /></a>}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 px-3 py-2.5">
              <span className="text-xs text-zinc-500">Their {PLATFORM_NAME[pick.platform]}{pick.handle ? <> · <span className="text-zinc-700 dark:text-zinc-300">{pick.handle}</span></> : null}</span>
              {readOnly || !campaignId ? (
                pick.url && <a href={pick.url} target="_blank" rel="noopener noreferrer" className={btn}>Open <ArrowUpRight size={12} /></a>
              ) : (
                <button type="button" className={btn} disabled={busy} onClick={() => measure(pick.platform)}>
                  {busy && <Loader2 size={12} className="animate-spin" />} Measure
                </button>
              )}
            </div>
          )}
          {error && <p role="status" className="text-[11px] text-rose-500">{error}</p>}
        </motion.div>
      )}
    </div>
  );
}
