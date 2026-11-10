"use client";

import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { SkippedSummary } from "@/data/influencerList";

/** A quiet chip: "347 checked · 31 kept ⓘ". Opens a popover with why the rest were left out.
 *  Hidden when the run kept no records (older campaigns) or the call fails: context, never a blocker. */
export function SkippedNote({ campaignId, api, ready }: {
  campaignId: string;
  api: (url: string) => Promise<{ data: SkippedSummary }>;
  ready: boolean; // fetch once the run has finished
}) {
  const [s, setS] = useState<SkippedSummary | null>(null);
  useEffect(() => {
    if (!ready) return;
    let live = true;
    api(`/api/campaigns/${campaignId}/skipped`)
      .then((r) => live && setS(r.data))
      .catch(() => live && setS(null));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api is a new function each render
  }, [campaignId, ready]);

  if (!s || !s.looked_at) return null;
  const kept = Math.max(0, s.looked_at - s.skipped);
  const max = Math.max(1, ...s.reasons.map((r) => r.count));
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-1.5 h-[30px] px-3 rounded-md border border-zinc-200 dark:border-zinc-800 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors whitespace-nowrap"
        >
          <span><span className="text-zinc-900 dark:text-zinc-100">{s.looked_at.toLocaleString()}</span> checked</span>
          <span className="text-zinc-300 dark:text-zinc-700">·</span>
          <span><span className="text-zinc-900 dark:text-zinc-100">{kept.toLocaleString()}</span> kept</span>
          <Info size={13} className="opacity-60" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-3 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
        <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100">How this list was made</p>
        <p className="mt-0.5 text-[11px] text-zinc-500">
          We checked {s.looked_at.toLocaleString()} creators and left out {s.skipped.toLocaleString()}:
        </p>
        <ul className="mt-2.5 space-y-1.5">
          {s.reasons.map((r) => (
            <li key={r.reason} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-0.5 text-[11px]">
              <span className="text-zinc-700 dark:text-zinc-300 first-letter:uppercase">{r.reason}</span>
              <span className="font-mono text-zinc-500">{r.count}</span>
              <span className="col-span-2 h-1 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
                <span className="block h-full rounded-full bg-zinc-400 dark:bg-zinc-500" style={{ width: `${(r.count / max) * 100}%` }} />
              </span>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
