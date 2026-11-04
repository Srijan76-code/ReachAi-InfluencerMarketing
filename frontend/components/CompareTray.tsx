"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import type { Influencer } from "@/data/influencerList";
import { compact, trendLabel } from "@/lib/posts";

export const MAX_COMPARE = 4;

type Row = {
  label: string;
  help?: string;
  value: (l: Influencer) => number | null; // for "best" highlighting; null = not comparable
  show: (l: Influencer) => string;
  better?: "high" | "low";
};

const num = (x: unknown) => (typeof x === "number" && Number.isFinite(x) ? x : null);
const live = (l: Influencer) => !l.data_expired;

const ROWS: Row[] = [
  { label: "Score", value: (l) => num(l.final_score), show: (l) => String(Math.round(l.final_score ?? 0)), better: "high" },
  { label: "Brand fit", value: (l) => num(l.score_parts?.fit), show: (l) => (l.score_parts ? `+${l.score_parts.fit.toFixed(1)}` : `${l.score_breakdown?.strategy_score ?? "—"}%`), better: "high" },
  { label: "Channel health", value: (l) => num(l.score_parts?.health), show: (l) => (l.score_parts ? `+${l.score_parts.health.toFixed(1)}` : `${l.score_breakdown?.health_score ?? "—"}%`), better: "high" },
  { label: "Risk", value: (l) => num(l.score_parts?.risk), show: (l) => (l.score_parts ? l.score_parts.risk.toFixed(1) : "—"), better: "high" },
  { label: "Subscribers", value: (l) => (live(l) ? num(l.subscribers) : null), show: (l) => (live(l) ? compact(l.subscribers) : "—"), better: "high" },
  { label: "Typical views", value: (l) => (live(l) ? num(l.metrics?.avg_views) : null), show: (l) => (live(l) ? compact(l.metrics?.avg_views) : "—"), better: "high" },
  { label: "Engagement", value: (l) => (live(l) ? num(l.metrics?.engagement_rate) : null), show: (l) => (live(l) && l.metrics?.engagement_rate != null ? `${l.metrics.engagement_rate}%` : "—"), better: "high" },
  { label: "Views trend", help: "Newest posts vs the ones before", value: (l) => (live(l) ? num(l.trend) : null), show: (l) => (live(l) ? trendLabel(l.trend)?.text ?? "—" : "—"), better: "high" },
  { label: "Posts matching your brief", value: (l) => (l.signals ? l.signals.fit_posts / Math.max(1, l.signals.posts_checked) : null), show: (l) => (l.signals ? `${l.signals.fit_posts} of ${l.signals.posts_checked}` : "—"), better: "high" },
  { label: "Sponsored posts", value: () => null, show: (l) => (l.signals ? `${l.signals.sponsored_posts}${l.signals.sponsor_brands.length ? ` (${l.signals.sponsor_brands.slice(0, 2).join(", ")})` : ""}` : "—") },
  { label: "Country", value: () => null, show: (l) => (l.country ? `${l.country}${l.country_source === "jev" ? " (judged)" : ""}` : "Unknown") },
  { label: "Fair price", help: "What one video is worth", value: (l) => (live(l) ? num(l.valuation) : null), show: (l) => (live(l) && l.valuation != null ? `$${Math.round(l.valuation)}` : "—"), better: "low" },
  { label: "Cost per 1k views", value: (l) => (live(l) ? num(l.estimated_cpm) : null), show: (l) => (live(l) && l.estimated_cpm != null ? `$${l.estimated_cpm}` : "—"), better: "low" },
];

function bestIndex(row: Row, leads: Influencer[]): number | null {
  if (!row.better) return null;
  const vals = leads.map(row.value);
  const known = vals.filter((v): v is number => v !== null);
  if (known.length < 2) return null;
  const target = row.better === "high" ? Math.max(...known) : Math.min(...known);
  if (known.filter((v) => v === target).length > 1) return null; // a tie has no winner
  return vals.indexOf(target);
}

function bestPost(l: Influencer) {
  const posts = (l.posts ?? []).filter((p) => p.x_usual !== null);
  return posts.sort((a, b) => (b.x_usual ?? 0) - (a.x_usual ?? 0))[0];
}

export function CompareTray({ leads, open, onOpenChange }: { leads: Influencer[]; open: boolean; onOpenChange: (o: boolean) => void }) {
  const shown = leads.slice(0, MAX_COMPARE);
  const cols = `160px repeat(${shown.length}, minmax(140px, 1fr))`;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl max-h-[85vh] overflow-y-auto bg-white dark:bg-[#0c0d0e]">
        <DialogHeader>
          <DialogTitle>Compare creators</DialogTitle>
          <DialogDescription>The best value in each row is highlighted.</DialogDescription>
        </DialogHeader>
        <div className="overflow-x-auto">
          <div className="min-w-fit text-[12px]" role="table" aria-label="Creator comparison">
            <div className="grid gap-3 pb-3 border-b border-zinc-200 dark:border-zinc-800" style={{ gridTemplateColumns: cols }} role="row">
              <div role="columnheader" />
              {shown.map((l) => (
                <div key={l.id} className="flex items-center gap-2 min-w-0" role="columnheader">
                  <CreatorAvatar name={l.title} src={l.avatar_url} className="w-8 h-8 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center shrink-0" textClassName="text-[12px] font-medium" />
                  <div className="min-w-0">
                    <a href={l.url || `https://www.youtube.com/channel/${l.id}`} target="_blank" rel="noopener noreferrer" className="block font-semibold text-zinc-900 dark:text-zinc-100 truncate hover:underline">
                      {l.title}
                    </a>
                    <span className="text-[10px] text-zinc-500">{l.deal_status}</span>
                  </div>
                </div>
              ))}
            </div>
            {ROWS.map((row) => {
              const best = bestIndex(row, shown);
              return (
                <div key={row.label} className="grid gap-3 py-2 border-b border-zinc-100 dark:border-zinc-900" style={{ gridTemplateColumns: cols }} role="row">
                  <div className="text-zinc-500" title={row.help} role="rowheader">{row.label}</div>
                  {shown.map((l, i) => (
                    <div key={l.id} role="cell" className={`font-mono ${best === i ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-zinc-800 dark:text-zinc-200"}`}>
                      {row.show(l)}
                    </div>
                  ))}
                </div>
              );
            })}
            <div className="grid gap-3 py-2" style={{ gridTemplateColumns: cols }} role="row">
              <div className="text-zinc-500" role="rowheader">Best recent post</div>
              {shown.map((l) => {
                const p = bestPost(l);
                return (
                  <div key={l.id} role="cell" className="min-w-0">
                    {p ? (
                      <a href={p.url || undefined} target="_blank" rel="noopener noreferrer" className="block hover:underline text-zinc-800 dark:text-zinc-200">
                        <span className="line-clamp-2">{p.title}</span>
                        <span className="font-mono text-[10px] text-emerald-600 dark:text-emerald-400">{p.x_usual?.toFixed(1)}× usual</span>
                      </a>
                    ) : (
                      <span className="text-zinc-500">—</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
