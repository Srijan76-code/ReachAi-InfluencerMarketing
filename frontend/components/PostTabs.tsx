"use client";

import { useEffect, useState } from "react";
import { PlayCircle, BadgeDollarSign } from "lucide-react";
import type { PostCard, PostSignals } from "@/data/influencerList";
import { ABOVE_USUAL_FROM, age, compact, defaultTab, postsFor, type PostTab } from "@/lib/posts";

const TABS: { key: PostTab; label: string; empty: string }[] = [
  { key: "match", label: "Best match", empty: "None of their recent posts mention your brief's topics." },
  { key: "above", label: "Above their usual", empty: `No recent post did ${ABOVE_USUAL_FROM}× better than usual.` },
  { key: "latest", label: "Latest", empty: "No recent posts." },
];

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
        <p className="text-[12px] text-zinc-500 leading-relaxed">
          <span className="font-medium text-zinc-700 dark:text-zinc-300">{signals.fit_posts}</span> of their last {signals.posts_checked} posts match your brief
          {signals.sponsored_posts > 0 && (
            <>
              {" · "}
              <span className="font-medium text-zinc-700 dark:text-zinc-300">{signals.sponsored_posts}</span> sponsored
              {signals.sponsor_brands.length > 0 && <> ({signals.sponsor_brands.join(", ")})</>}
            </>
          )}
          {signals.median_reach !== null && <> · usually {compact(signals.median_reach)} {posts[0]?.reach_label === "likes" ? "likes" : "views"}</>}
        </p>
      )}

      <div role="tablist" aria-label="Posts" className="flex items-center gap-1 p-0.5 rounded-md bg-zinc-100 dark:bg-zinc-900/60 border border-zinc-200/60 dark:border-zinc-800/60 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${tab === t.key ? "bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-sm" : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"}`}
          >
            {t.label} <span className="font-mono opacity-60">{counts[t.key]}</span>
          </button>
        ))}
      </div>

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
