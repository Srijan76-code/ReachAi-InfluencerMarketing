"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Eye, Lock } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sheet } from "@/components/ui/sheet";
import { InfluencerRow } from "@/app/ListOfInfluencer/InfluencerRow";
import { InfluencerDetailSheet } from "@/app/ListOfInfluencer/InfluencerDetailSheet";
import { CompareTray, MAX_COMPARE } from "@/components/CompareTray";
import { LeadListSkeleton } from "@/components/LeadListSkeleton";
import type { Influencer } from "@/data/influencerList";

type Shared = {
  campaign_name: string;
  shared_by: string | null;
  role: string;
  show_prices: boolean;
  expires_at: string | null;
  creators: Influencer[];
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** A read-only shortlist someone shared. No sign-in: the link is the permission. */
export default function SharedShortlist({ token }: { token: string }) {
  const [data, setData] = useState<Shared | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [compareOpen, setCompareOpen] = useState(false);

  useEffect(() => {
    let live = true;
    fetch(`${BACKEND}/api/share/${encodeURIComponent(token)}`, { cache: "no-store", referrerPolicy: "no-referrer" })
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!live) return;
        if (r.ok) setData(body as Shared);
        else setError(typeof body?.detail === "string" ? body.detail : "This link can't be opened.");
      })
      .catch(() => live && setError("Couldn't load this shortlist. Check your connection and try again."));
    return () => {
      live = false;
    };
  }, [token]);

  const toggle = (id: string) =>
    setPicked((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else if (n.size < MAX_COMPARE) n.add(id);
      return n;
    });

  const expires = data?.expires_at ? Math.max(0, Math.ceil((Date.parse(data.expires_at) - Date.now()) / 86_400_000)) : null;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] text-zinc-600 dark:text-zinc-400 pt-24 pb-16 px-4 sm:px-8 font-sans">
        <div className="max-w-7xl mx-auto space-y-5">
          {error ? (
            <div className="max-w-md mx-auto mt-16 text-center space-y-3">
              <Lock size={22} className="mx-auto text-zinc-400" />
              <h1 className="text-base font-medium text-zinc-900 dark:text-zinc-100">{error}</h1>
              <p className="text-xs text-zinc-500">Ask the person who shared it for a new link.</p>
            </div>
          ) : !data ? (
            <LeadListSkeleton />
          ) : (
            <>
              <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 px-1">
                <div>
                  <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-zinc-400">Shared shortlist</p>
                  <h1 className="mt-1 text-lg font-medium text-zinc-900 dark:text-zinc-100">{data.campaign_name}</h1>
                  <p className="mt-1 text-xs text-zinc-500 flex flex-wrap items-center gap-x-2">
                    {data.shared_by && <span>Shared by {data.shared_by}</span>}
                    <span className="flex items-center gap-1"><Eye size={12} /> View only</span>
                    {expires !== null && <span>Link expires in {expires} day{expires === 1 ? "" : "s"}</span>}
                    {!data.show_prices && <span>Prices hidden by the sender</span>}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-zinc-500">{picked.size ? `${picked.size} picked` : `Tick up to ${MAX_COMPARE} to compare`}</span>
                  <button
                    type="button"
                    disabled={picked.size < 2}
                    onClick={() => setCompareOpen(true)}
                    className="px-3 py-1.5 font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Compare
                  </button>
                </div>
              </header>

              {data.creators.length === 0 ? (
                <p className="text-sm text-zinc-500 px-1">No creators in this shortlist.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {data.creators.map((c, i) => (
                    <div key={c.id} className="flex items-stretch gap-2">
                      <label className="w-10 rounded-lg border border-zinc-200/50 dark:border-zinc-800/50 bg-white dark:bg-[#0c0d0e] flex items-center justify-center cursor-pointer" title="Pick to compare">
                        <input
                          type="checkbox"
                          aria-label={`Compare ${c.title}`}
                          checked={picked.has(c.id)}
                          disabled={!picked.has(c.id) && picked.size >= MAX_COMPARE}
                          onChange={() => toggle(c.id)}
                          className="accent-zinc-900 dark:accent-zinc-100"
                        />
                      </label>
                      <div className="flex-1 min-w-0">
                        <Sheet open={openId === c.id} onOpenChange={(o) => setOpenId(o ? c.id : null)}>
                          <div
                            role="button"
                            tabIndex={0}
                            onClick={() => setOpenId(c.id)}
                            onKeyDown={(e) => e.key === "Enter" && setOpenId(c.id)}
                            className="h-full rounded-lg border border-zinc-200/50 dark:border-zinc-800/50 hover:border-zinc-300/50 dark:hover:border-zinc-700/50 overflow-hidden cursor-pointer"
                          >
                            <InfluencerRow influencer={c} rank={i + 1} readOnly />
                          </div>
                          <InfluencerDetailSheet influencer={c} readOnly />
                        </Sheet>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <footer className="pt-6 text-center text-xs text-zinc-500">
                Made with <Link href="/" className="font-medium text-zinc-800 dark:text-zinc-200 hover:underline">ReachAI</Link>: find the influencers who will actually convert, with a fair price for each.
              </footer>

              <CompareTray open={compareOpen} onOpenChange={setCompareOpen} leads={data.creators.filter((c) => picked.has(c.id))} />
            </>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
