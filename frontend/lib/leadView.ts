import type { Influencer } from "@/data/influencerList";

/** How the results list is filtered and sorted. Pure functions: the page keeps the state. */

export type SortKey = "optimal" | "yield" | "authority" | "budget" | "value" | "reach" | "engagement";

export const SORTS: { key: SortKey; label: string }[] = [
  { key: "optimal", label: "Best match (score)" },
  { key: "value", label: "Best value (cost per 1k views)" },
  { key: "reach", label: "Most views" },
  { key: "engagement", label: "Highest engagement" },
  { key: "yield", label: "High intent (yield)" },
  { key: "authority", label: "Authority (trust)" },
  { key: "budget", label: "Lowest price" },
];

export type LeadView = {
  sort: SortKey;
  query: string;
  confidence: "All" | "Strong Buy" | "Consider+";
  reliability: "All" | "High" | "Stable";
  price: "All" | "Micro" | "Mid" | "Premium";
  platforms: string[]; // empty = all
  rising: boolean;
  onTrend: boolean;
  hideSuspicious: boolean;
  savedOnly: boolean;
  approved: boolean; // reviewers gave more 👍 than 👎
  hasFeedback: boolean;
};

export const DEFAULT_VIEW: LeadView = {
  sort: "optimal",
  query: "",
  confidence: "All",
  reliability: "All",
  price: "All",
  platforms: [],
  rising: false,
  onTrend: false,
  hideSuspicious: false,
  savedOnly: false,
  approved: false,
  hasFeedback: false,
};

/** Number of filters that differ from the default (sort, search and the All | Shortlist switch are not counted). */
export function activeFilterCount(v: LeadView): number {
  return (
    Number(v.confidence !== "All") +
    Number(v.reliability !== "All") +
    Number(v.price !== "All") +
    Number(v.platforms.length > 0) +
    Number(v.rising) +
    Number(v.onTrend) +
    Number(v.hideSuspicious) +
    Number(v.approved) +
    Number(v.hasFeedback)
  );
}

export function platformOf(lead: Influencer): string {
  return (lead.platform || "youtube").toLowerCase();
}

/** Platforms present in these results, with counts, most first. */
export function platformCounts(leads: Influencer[]): { platform: string; count: number }[] {
  const m = new Map<string, number>();
  for (const l of leads) m.set(platformOf(l), (m.get(platformOf(l)) ?? 0) + 1);
  return [...m.entries()].map(([platform, count]) => ({ platform, count })).sort((a, b) => b.count - a.count);
}

const num = (x: unknown): number | null => (typeof x === "number" && Number.isFinite(x) ? x : null);

/** Sort value, higher first; null sorts last whatever the direction. */
function sortValue(l: Influencer, key: SortKey): number | null {
  switch (key) {
    case "optimal":
      return num(l.final_score);
    case "yield":
      return parseInt(String(l.metrics?.forecast ?? "").replace(/[^0-9]/g, "")) || null;
    case "authority":
      return num(l.metrics?.trust_score);
    case "budget":
      return num(l.valuation) === null ? null : -(l.valuation as number); // cheapest first
    case "value": {
      const c = num(l.estimated_cpm);
      return c === null || c <= 0 ? null : -c; // lowest cost per 1k views first
    }
    case "reach":
      return l.data_expired ? null : num(l.metrics?.avg_views);
    case "engagement":
      return l.data_expired ? null : num(l.metrics?.engagement_rate);
  }
}

/** Reviewer feedback per creator, for the "Approved by reviewers" / "Has feedback" filters. */
export type FeedbackCounts = Record<string, { yes: number; no: number; comments: number }>;

export function applyView(
  leads: Influencer[] | null | undefined,
  v: LeadView,
  saved: Record<string, boolean>,
  feedback: FeedbackCounts = {},
): Influencer[] {
  if (!Array.isArray(leads)) return [];
  const q = v.query.trim().toLowerCase();
  const out = leads.filter((l) => {
    const flags = l.flags ?? [];
    if (q && !`${l.title ?? ""} ${l.niche ?? ""} ${l.description ?? ""}`.toLowerCase().includes(q)) return false;
    if (v.confidence === "Strong Buy" && l.deal_status !== "Strong Buy") return false;
    if (v.confidence === "Consider+" && l.deal_status === "Avoid") return false;
    const rel = l.metrics?.reliability;
    if (v.reliability === "High" && rel !== "High") return false;
    if (v.reliability === "Stable" && rel !== "High" && rel !== "Medium") return false;
    const price = l.valuation || 0;
    if (v.price === "Micro" && price >= 300) return false;
    if (v.price === "Mid" && (price < 300 || price > 1000)) return false;
    if (v.price === "Premium" && price <= 1000) return false;
    if (v.platforms.length && !v.platforms.includes(platformOf(l))) return false;
    if (v.rising && !(l.rising || flags.includes("rising"))) return false;
    if (v.onTrend && !flags.includes("trend")) return false;
    if (v.hideSuspicious && flags.includes("suspicious")) return false;
    if (v.savedOnly && !saved[l.id]) return false;
    const fb = feedback[l.id];
    if (v.approved && !(fb && fb.yes > fb.no)) return false;
    if (v.hasFeedback && !(fb && fb.yes + fb.no + fb.comments > 0)) return false;
    return true;
  });
  // stable sort: ties keep the engine's order
  return out
    .map((l, i) => ({ l, i, s: sortValue(l, v.sort) }))
    .sort((a, b) => (a.s === null ? (b.s === null ? a.i - b.i : 1) : b.s === null ? -1 : b.s - a.s || a.i - b.i))
    .map((x) => x.l);
}

/** Restore a saved view, ignoring anything unknown (older versions, hand edits). */
export function parseView(raw: string | null): LeadView {
  if (!raw) return DEFAULT_VIEW;
  try {
    const o = JSON.parse(raw);
    const v = { ...DEFAULT_VIEW };
    if (SORTS.some((s) => s.key === o.sort)) v.sort = o.sort;
    if (["All", "Strong Buy", "Consider+"].includes(o.confidence)) v.confidence = o.confidence;
    if (["All", "High", "Stable"].includes(o.reliability)) v.reliability = o.reliability;
    if (["All", "Micro", "Mid", "Premium"].includes(o.price)) v.price = o.price;
    if (Array.isArray(o.platforms)) v.platforms = o.platforms.filter((p: unknown) => typeof p === "string");
    for (const k of ["rising", "onTrend", "hideSuspicious", "savedOnly", "approved", "hasFeedback"] as const) v[k] = o[k] === true;
    return v; // the search box is not restored: it surprises people on return
  } catch {
    return DEFAULT_VIEW;
  }
}
