/** Track (spec §7.6; backend app/api/routes/track.py). */

export type GoalKind = "signups" | "sales" | "views" | "clicks";
export const GOAL_KINDS: { value: GoalKind; label: string; one: string }[] = [
  { value: "signups", label: "Signups", one: "signup" },
  { value: "sales", label: "Sales", one: "sale" },
  { value: "views", label: "Views", one: "view" },
  { value: "clicks", label: "Clicks", one: "click" },
];
export const PAY_METHODS = [
  ["paypal", "PayPal"],
  ["bank", "Bank transfer"],
  ["upi", "UPI"],
  ["wise", "Wise"],
  ["other", "Other"],
] as const;

export type CommentSummary = {
  disabled?: boolean;
  count?: number;
  sentiment?: string;
  product_interest?: boolean;
  product_questions?: boolean;
  ad_backlash?: boolean;
  top?: string[];
  read_at?: string;
};

export type TrackPost = {
  id: string;
  deal_id: string;
  name: string;
  avatar_url: string | null;
  deliverable: string;
  due_on: string | null;
  video_id: string | null;
  title: string | null;
  thumbnail_url: string | null;
  url: string | null;
  live_at: string | null;
  found_by: "link" | "code" | "jev" | "you" | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  comment_summary: CommentSummary | null;
  spark: { day: string; views: number }[];
  state: "live" | "late" | "due";
};

export type TrackCreator = {
  deal_id: string;
  name: string;
  avatar_url: string | null;
  cost: number;
  views: number;
  clicks: number;
  results: number;
  code: string | null;
  link: { url: string; target: string } | null;
  cost_per_1k_views: number | null;
  cost_per_result: number | null;
  expected_views: number | null;
  verdict: "rebook" | "ok" | "skip" | "too_early";
  why: string;
  conversions: Record<string, number>;
};

export type Track = {
  goal: { kind: GoalKind; count: number | null; value_each: number | null };
  totals: {
    spent: number; paid: number; views: number; clicks: number; results: number; signups: number; code_uses: number;
    cost_per_result: number | null; cost_per_1k_views: number | null; value: number | null; return: number | null;
  };
  forecast: { views: number; results: number; by: string | null; estimate: true } | null;
  series: { day: string; views: number; clicks: number; results: number }[];
  posts: TrackPost[];
  creators: TrackCreator[];
  to_pay: { deal_id: string; name: string; avatar_url: string | null; amount: number; why: string }[];
  paid: { deal_id: string; name: string; amount: number; paid_at: string | null; method: string | null }[];
  snippet: { key: string; src: string };
  refreshed_at: string | null;
  budget: number | null;
};
