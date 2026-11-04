/** Deals (spec §8.1; backend app/api/routes/deals.py). */

export const STAGES = ["contacted", "negotiating", "agreed", "content", "live", "paid", "lost"] as const;
export type Stage = (typeof STAGES)[number];
export const BOARD_STAGES: Stage[] = ["contacted", "negotiating", "agreed", "content", "live", "paid"];

export const STAGE_LABEL: Record<Stage, string> = {
  contacted: "Contacted",
  negotiating: "Negotiating",
  agreed: "Agreed",
  content: "Content",
  live: "Live",
  paid: "Paid",
  lost: "Lost",
};
export const STAGE_HINT: Record<Stage, string> = {
  contacted: "You reached out",
  negotiating: "Talking price and terms",
  agreed: "Price and terms agreed",
  content: "They're making it",
  live: "The post is up",
  paid: "You paid them",
  lost: "Not going ahead",
};

export const DELIVERABLES = [
  ["integration", "Sponsored segment"],
  ["dedicated", "Dedicated video"],
  ["short", "Short"],
  ["post", "Post"],
  ["story", "Story"],
] as const;
export const DEAL_TYPES = [
  ["flat", "Flat fee"],
  ["base_plus_commission", "Fee + commission"],
  ["affiliate", "Commission only"],
  ["gifted", "Gifted product"],
] as const;
export const USAGE = [
  ["none", "Their channel only"],
  ["organic", "We can repost it"],
  ["paid_30", "Paid ads, 30 days"],
  ["paid_60", "Paid ads, 60 days"],
  ["paid_90", "Paid ads, 90 days"],
] as const;

export type Advice = {
  fair_low: number | null;
  fair_high: number | null;
  verdict: "great" | "accept" | "counter" | "walk_away" | null;
  counter: number | null;
  reason: string;
};

export type Deal = {
  id: string;
  creator_id: string;
  platform: string;
  name: string;
  avatar_url: string | null;
  url: string | null;
  country: string | null;
  deal_status: string | null;
  final_score: number | null;
  forecast: string | null;
  stage: Stage;
  position: number;
  deliverable: string;
  post_by: string | null;
  deal_type: string;
  commission_pct: number | null;
  usage_rights: string;
  exclusivity_days: number;
  disclosure: boolean;
  currency: string;
  quoted_rate: number | null;
  agreed_rate: number | null;
  typical_views: number | null;
  advice: Advice;
  post_url: string | null;
  live_at: string | null;
  paid_amount: number | null;
  paid_at: string | null;
  payment_ref: string | null;
  notes: string | null;
  overdue: boolean;
  updated_at: string | null;
};

export type DealsSummary = {
  deals: number;
  by_stage: Record<Stage, number>;
  committed: number;
  paid: number;
  budget: number | null;
  over_budget: boolean;
  live: number;
  agreed: number;
};

export type DealEvent = { type: string; payload: Record<string, unknown> | null; at: string | null };

export type CounterOut = {
  advice: Advice;
  angle: "accept" | "budget" | "performance" | "scope";
  signals: Record<string, number | boolean>;
  amounts: Record<string, number>;
  message: string;
  source: "ai" | "template";
};

export const money = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `$${Math.round(n).toLocaleString()}`;
