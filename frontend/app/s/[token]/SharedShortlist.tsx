"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Eye, Lock, MessageSquare } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sheet } from "@/components/ui/sheet";
import { InfluencerRow } from "@/app/ListOfInfluencer/InfluencerRow";
import { InfluencerDetailSheet } from "@/app/ListOfInfluencer/InfluencerDetailSheet";
import { CompareTray, MAX_COMPARE } from "@/components/CompareTray";
import { LeadListSkeleton } from "@/components/LeadListSkeleton";
import { ReviewBox, VerdictButtons, type MyFeedback } from "@/components/Feedback";
import type { Influencer } from "@/data/influencerList";

type Shared = {
  campaign_name: string;
  shared_by: string | null;
  role: string;
  show_prices: boolean;
  expires_at: string | null;
  creators: Influencer[];
  can_review: boolean;
  my_feedback: Record<string, MyFeedback>;
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
async function call(path: string, init?: RequestInit) {
  const r = await fetch(`${BACKEND}${path}`, { cache: "no-store", referrerPolicy: "no-referrer", ...init });
  const body = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, body };
}

/** A shortlist someone shared. No sign-in: the link is the permission. */
export default function SharedShortlist({ token }: { token: string }) {
  const [data, setData] = useState<Shared | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [compareOpen, setCompareOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await call(`/api/share/${encodeURIComponent(token)}`);
      if (r.ok) setData(r.body as Shared);
      else setError(typeof r.body?.detail === "string" ? r.body.detail : "This link can't be opened.");
    } catch {
      setError("Couldn't load this shortlist. Check your connection and try again.");
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (id: string) =>
    setPicked((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else if (n.size < MAX_COMPARE) n.add(id);
      return n;
    });

  // reviewer: save a verdict/comment (optimistic for the thumbs, confirmed for the comment box)
  const saveFeedback = async (creatorId: string, v: MyFeedback): Promise<boolean> => {
    const before = data?.my_feedback[creatorId];
    setData((d) => (d ? { ...d, my_feedback: { ...d.my_feedback, [creatorId]: v } } : d));
    const r = await call(`/api/share/${encodeURIComponent(token)}/feedback/${encodeURIComponent(creatorId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v),
    }).catch(() => ({ ok: false }));
    if (!r.ok) setData((d) => (d ? { ...d, my_feedback: { ...d.my_feedback, [creatorId]: before ?? { verdict: null, comment: null } } } : d));
    return r.ok;
  };

  const expires = data?.expires_at ? Math.max(0, Math.ceil((Date.parse(data.expires_at) - Date.now()) / 86_400_000)) : null;
  const reviewed = data ? Object.values(data.my_feedback).filter((f) => f.verdict).length : 0;

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
                  <p className="text-[11px] font-medium text-zinc-400">Shared shortlist</p>
                  <h1 className="mt-1 text-lg font-medium text-zinc-900 dark:text-zinc-100">{data.campaign_name}</h1>
                  <p className="mt-1 text-xs text-zinc-500 flex flex-wrap items-center gap-x-2">
                    {data.shared_by && <span>Shared by {data.shared_by}</span>}
                    {data.can_review ? (
                      <span className="flex items-center gap-1"><MessageSquare size={12} /> You can approve or reject each creator · {reviewed} of {data.creators.length} done</span>
                    ) : (
                      <span className="flex items-center gap-1"><Eye size={12} /> View only</span>
                    )}
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
                    className="h-[30px] px-3 font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40"
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
                      <label className="w-10 rounded-lg border border-zinc-200/50 dark:border-zinc-800/50 bg-white dark:bg-[#0c0d0e] flex items-center justify-center" title="Pick to compare">
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
                            className={`h-full rounded-lg border overflow-hidden ${openId === c.id ? "border-zinc-400 dark:border-zinc-500" : "border-zinc-200/50 dark:border-zinc-800/50 hover:border-zinc-300/50 dark:hover:border-zinc-700/50"}`}
                          >
                            <InfluencerRow influencer={c} rank={i + 1} readOnly />
                          </div>
                          <InfluencerDetailSheet
                            influencer={c}
                            readOnly
                            reviewSlot={data.can_review ? (
                              <ReviewBox value={data.my_feedback[c.id]} onSave={(v) => saveFeedback(c.id, v)} />
                            ) : undefined}
                          />
                        </Sheet>
                      </div>
                      {data.can_review && (
                        <div className="w-10 flex items-center justify-center">
                          <VerdictButtons name={c.title} value={data.my_feedback[c.id]} onChange={(v) => saveFeedback(c.id, v)} />
                        </div>
                      )}
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
