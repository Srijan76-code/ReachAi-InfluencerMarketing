"use client";

import type React from "react";
import { useEffect, useState } from "react";
import { PlayCircle, BadgeDollarSign, Eye, Target } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Segmented } from "@/components/ui/segmented";
import type { PostCard, PostSignals } from "@/data/influencerList";
import { ABOVE_USUAL_FROM, age, compact, defaultTab, postsFor, type PostTab } from "@/lib/posts";

const TABS: { key: PostTab; label: string; empty: string }[] = [
  { key: "match", label: "Best match", empty: "None of their recent posts mention your brief's topics." },
  { key: "above", label: "Above their usual", empty: `No recent post did ${ABOVE_USUAL_FROM}× better than usual.` },
  { key: "latest", label: "Latest", empty: "No recent posts." },
];

/** One tile in the summary strip, styled like the panel's Performance metrics cells. */
function Stat({ icon, label, value, help, last = false }: { icon: React.ReactNode; label: string; value: React.ReactNode; help: string; last?: boolean }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className={`p-3 flex flex-col gap-1.5 min-w-0 cursor-help hover:bg-zinc-100 dark:hover:bg-zinc-800/20 transition-colors ${last ? "" : "border-r border-zinc-200/60 dark:border-zinc-800/60"}`}>
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-zinc-400 dark:text-zinc-600 shrink-0">{icon}</span>
            <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400 truncate">{label}</span>
          </div>
          <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-200 pl-[1.125rem] truncate">{value}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs shadow-xl max-w-[220px] text-zinc-700 dark:text-zinc-300">
        {help}
      </TooltipContent>
    </Tooltip>
  );
}

function Thumb({ src }: { src: string | null }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  return (
    <div className="w-16 aspect-video shrink-0 rounded-[4px] overflow-hidden bg-zinc-200/70 dark:bg-zinc-800/70 flex items-center justify-center">
      {src && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote platform thumbnail
        <img src={src} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" className="w-full h-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <PlayCircle size={14} className="text-zinc-400 dark:text-zinc-600" />
      )}
    </div>
  );
}

export function PostTabs({ posts, signals, fallbackUrl }: { posts: PostCard[]; signals?: PostSignals | null; fallbackUrl: string }) {
  const [tab, setTab] = useState<PostTab>(() => defaultTab(posts));
  useEffect(() => setTab(defaultTab(posts)), [posts]); // a different creator opened in the same panel
  const shown = postsFor(tab, posts).slice(0, 6);
  const counts = { match: postsFor("match", posts).length, above: postsFor("above", posts).length, latest: posts.length };

  return (
    <div className="space-y-3">
      {signals && signals.posts_checked > 0 && (
        <div className="grid grid-cols-3 rounded border border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-100 dark:bg-[#121314] overflow-hidden">
          <Stat
            icon={<Target size={13} />}
            label="On brief"
            value={<>{signals.fit_posts}<span className="text-zinc-500 font-normal"> / {signals.posts_checked}</span></>}
            help={`${signals.fit_posts} of their last ${signals.posts_checked} posts are about your brief's topics.`}
          />
          <Stat
            icon={<BadgeDollarSign size={13} />}
            label="Sponsored"
            value={<>{signals.sponsored_posts}<span className="text-zinc-500 font-normal"> / {signals.posts_checked}</span></>}
            help={signals.sponsor_brands.length ? `Recent sponsors: ${signals.sponsor_brands.join(", ")}` : "Posts that say they're a paid promotion."}
          />
          <Stat
            icon={<Eye size={13} />}
            label={posts[0]?.reach_label === "likes" ? "Usual likes" : "Usual views"}
            value={compact(signals.median_reach)}
            help="What a typical recent post gets: the middle value, so one viral post doesn't skew it."
            last
          />
        </div>
      )}

      <Segmented
        label="Posts"
        size="sm"
        value={tab}
        onChange={setTab}
        options={TABS.map((t) => ({ value: t.key, label: t.label, count: counts[t.key] }))}
      />

      <div role="tabpanel" className="rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-100 dark:bg-[#121314] overflow-hidden divide-y divide-zinc-200/60 dark:divide-zinc-800/60">
        {shown.length === 0 ? (
          <p className="p-4 text-[12px] text-zinc-500">{TABS.find((t) => t.key === tab)?.empty}</p>
        ) : (
          shown.map((p, i) => (
            <a
              key={p.id ?? i}
              href={p.url || fallbackUrl}
              target="_blank"
              rel="noopener noreferrer"
              title={p.url ? "Open the post" : "Open the creator's posts"}
              className="flex items-center gap-3 p-2.5 hover:bg-zinc-200/40 dark:hover:bg-zinc-800/30 transition-colors group"
            >
              <Thumb src={p.thumbnail_url} />
              <div className="min-w-0 flex-1 flex flex-col gap-1">
                <span className="text-[12px] text-zinc-700 dark:text-zinc-300 truncate group-hover:text-zinc-900 dark:group-hover:text-zinc-100">{p.title || "Untitled post"}</span>
                <div className="flex items-center gap-1.5 flex-wrap text-[10px]">
                  {p.matched_topics.slice(0, 2).map((t) => (
                    <span key={t} className="px-1.5 py-px rounded border border-blue-500/20 bg-blue-500/10 text-blue-600 dark:text-blue-400">{t}</span>
                  ))}
                  {p.sponsored && (
                    <span className="px-1.5 py-px rounded border border-violet-500/20 bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center gap-0.5">
                      <BadgeDollarSign size={10} /> Sponsored
                    </span>
                  )}
                  {p.format === "short" && <span className="text-zinc-500">Short</span>}
                  {p.published_at && <span className="text-zinc-500">{age(p.published_at)}</span>}
                </div>
              </div>
              <div className="shrink-0 text-right flex flex-col gap-0.5">
                <span className="font-mono text-[11px] text-zinc-700 dark:text-zinc-300">{compact(p.reach)}</span>
                {p.is_new && p.x_usual === null && (
                  <span className="text-[10px] text-zinc-500" title="Under a week old: still collecting views">New</span>
                )}
                {p.x_usual !== null && (
                  <span className={`font-mono text-[10px] ${p.x_usual >= ABOVE_USUAL_FROM ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-500"}`}>
                    {p.x_usual.toFixed(1)}× usual
                  </span>
                )}
              </div>
            </a>
          ))
        )}
      </div>
    </div>
  );
}
