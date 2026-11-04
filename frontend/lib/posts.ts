import type { PostCard } from "@/data/influencerList";

/** Sorting and labels for the creator panel's post tabs. Pure functions; numbers come from the backend. */

export type PostTab = "match" | "above" | "latest";

export const ABOVE_USUAL_FROM = 1.5; // same as backend app/metrics/constants.py

const time = (p: PostCard) => (p.published_at ? Date.parse(p.published_at) || 0 : 0);

export function postsFor(tab: PostTab, posts: PostCard[] | undefined | null): PostCard[] {
  const all = Array.isArray(posts) ? posts : [];
  if (tab === "latest") return [...all].sort((a, b) => time(b) - time(a));
  if (tab === "above")
    return all
      .filter((p) => (p.x_usual ?? 0) >= ABOVE_USUAL_FROM)
      .sort((a, b) => (b.x_usual ?? 0) - (a.x_usual ?? 0));
  return all
    .filter((p) => p.matched_topics?.length)
    .sort((a, b) => b.matched_topics.length - a.matched_topics.length || (b.x_usual ?? 0) - (a.x_usual ?? 0) || time(b) - time(a));
}

/** Open on the tab that has something to show: best match, else above usual, else latest. */
export function defaultTab(posts: PostCard[] | undefined | null): PostTab {
  if (postsFor("match", posts).length) return "match";
  if (postsFor("above", posts).length) return "above";
  return "latest";
}

export function compact(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 100_000 ? 0 : 1)}k`;
  return String(Math.round(n));
}

/** "today", "3d", "5w", "4mo", "2y" */
export function age(iso: string | null | undefined, now: number = Date.now()): string {
  const t = iso ? Date.parse(iso) : NaN;
  if (!Number.isFinite(t)) return "";
  const d = Math.max(0, Math.floor((now - t) / 86_400_000));
  if (d === 0) return "today";
  if (d < 14) return `${d}d`;
  if (d < 60) return `${Math.floor(d / 7)}w`;
  if (d < 730) return `${Math.floor(d / 30)}mo`;
  return `${Math.floor(d / 365)}y`;
}

/** "Numbers from today" / "Numbers from 3 days ago" / null when unknown. */
export function freshness(iso: string | null | undefined, now: number = Date.now()): string | null {
  const t = iso ? Date.parse(iso) : NaN;
  if (!Number.isFinite(t)) return null;
  const d = Math.max(0, Math.floor((now - t) / 86_400_000));
  if (d === 0) return "Numbers from today";
  if (d === 1) return "Numbers from yesterday";
  return `Numbers from ${d} days ago`;
}

/** Trend label from momentum (recent posts' reach ÷ older posts'). */
export function trendLabel(trend: number | null | undefined): { text: string; tone: "up" | "down" | "flat" } | null {
  if (trend === null || trend === undefined || !Number.isFinite(trend)) return null;
  if (trend >= 1.15) return { text: `Up ${trend.toFixed(1)}×`, tone: "up" };
  if (trend <= 0.85) return { text: `Down to ${trend.toFixed(1)}×`, tone: "down" };
  return { text: "Steady", tone: "flat" };
}
