"use client";

import { useEffect, useState } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { SkippedSummary } from "@/data/influencerList";

/** "Looked at 312 creators · 288 left out: inactive 120, too few views 80 …" from /skipped.
 *  Hidden when the run kept no records (older campaigns) or the call fails: it's extra context, never a blocker. */
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
  const top = s.reasons.slice(0, 3);
  const more = s.reasons.length - top.length;
  return (
    <p className="text-[11px] text-zinc-500 dark:text-zinc-500 leading-relaxed">
      Looked at <span className="font-medium text-zinc-700 dark:text-zinc-300">{s.looked_at.toLocaleString()}</span> creators
      {s.skipped > 0 && (
        <>
          {" · "}
          <span className="font-medium text-zinc-700 dark:text-zinc-300">{s.skipped.toLocaleString()}</span> left out
          {top.length > 0 && ": "}
          {top.map((r, i) => (
            <span key={r.reason}>
              {i > 0 && ", "}
              {r.reason} {r.count}
            </span>
          ))}
          {more > 0 && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="ml-1 underline decoration-dotted underline-offset-2 hover:text-zinc-700 dark:hover:text-zinc-300">
                  +{more} more
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-800 dark:text-zinc-200">
                <ul className="space-y-0.5">
                  {s.reasons.map((r) => (
                    <li key={r.reason} className="flex justify-between gap-4">
                      <span>{r.reason}</span>
                      <span className="font-mono">{r.count}</span>
                    </li>
                  ))}
                </ul>
              </TooltipContent>
            </Tooltip>
          )}
        </>
      )}
    </p>
  );
}
