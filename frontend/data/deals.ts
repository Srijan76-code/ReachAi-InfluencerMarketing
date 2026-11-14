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
  quoted_commission_pct?: number | null; // the commission they asked for, as the agent read it
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
  contact_email?: string | null;
  emailing?: boolean; // an email thread with them exists in the founder's Gmail
  last_message?: { who: "you" | "them"; text: string; at: string | null } | null; // for the inbox list
  unread?: number; // their replies since you last opened the chat
  last_read_at?: string | null;
  channel?: Channel; // how you reach them (picked from what we have unless you chose)
  channel_set?: boolean;
  socials?: Partial<Record<"instagram" | "twitter" | "linkedin", string>>;
  // where ReachAI found their email (and whether AI checked it), that it found none, or an earlier contact
  contact?: { source?: "bio" | "link_page" | "website"; checked?: boolean; none?: boolean; contacted_before?: string | null } | null;
  pay_when?: string | null;
  tracking_code?: string | null;
  posts?: DealPost[]; // what they agreed to post (only on the list, and after agreeing)
  link?: { url: string; slug: string; target: string; clicks: number } | null;
  writing?: boolean; // ReachAI is still writing their first message
};

export type DealPost = { id: string; deliverable: string; due_on: string | null; post_url: string | null; live_at: string | null };

export type Channel = "email" | "instagram" | "twitter" | "linkedin" | "whatsapp" | "other";
export const CHANNELS: { value: Channel; label: string; verb: string }[] = [
  { value: "email", label: "Email", verb: "Send" },
  { value: "instagram", label: "Instagram DM", verb: "Copy and open Instagram" },
  { value: "twitter", label: "X DM", verb: "Copy and open X" },
  { value: "linkedin", label: "LinkedIn message", verb: "Copy and open LinkedIn" },
  { value: "whatsapp", label: "WhatsApp", verb: "Copy and open WhatsApp" },
  { value: "other", label: "Somewhere else", verb: "Copy" },
];
export const PAY_WHEN = [
  ["on_live", "When the post is live"],
  ["half_half", "Half now, half when live"],
  ["upfront", "Before they post"],
  ["net_7", "7 days after it's live"],
] as const;

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

/** A next step the agent suggests (the "Needs you" queue): nothing happens until you approve it. */
export type Proposal = {
  id: string;
  deal_id: string;
  kind: "record_quote" | "send_counter" | "agree" | "follow_up" | "chase_post" | "mark_live" | "mark_paid" | "mark_lost" | "hold_terms" | "pitch" | "confirm_terms";
  title: string;
  reason: string | null;
  message: string | null;
  source: "ai" | "template";
  can_reword: boolean;
  is_message: boolean;
  can_send?: boolean; // Gmail connected and we have their email: approving sends it
  terms?: { fee: number | null; commission_pct: number | null; structure?: string } | null; // what the message offers
  change?: { from: Offer; to: Offer } | null; // hold_terms: after agreeing, they asked for more
  subject?: string | null; // a first email's subject line
  texts?: Partial<Record<string, { subject?: string; body: string }>> | null; // pitch: the message for each channel
  seen?: boolean; // you've looked at this first message ("Send all reviewed")
  needs_review?: boolean; // a first message that failed ReachAI's checks: fix it before sending ("Send all" skips it)
  problems?: string[]; // what the checks found
  name: string;
  avatar_url: string | null;
  created_at: string | null;
};

type Offer = { fee: number | null; commission_pct: number | null };

/** Suggestions that are a message in the chat (they show up in the message box). */
export const CHAT_KINDS: Proposal["kind"][] = ["send_counter", "agree", "mark_lost", "follow_up", "hold_terms", "pitch", "confirm_terms", "chase_post"];

export const PROPOSAL_ACTION: Record<Proposal["kind"], string> = {
  hold_terms: "Copy and mark sent",
  pitch: "Copy and mark sent",
  confirm_terms: "Copy and mark sent",
  record_quote: "Write it down",
  send_counter: "Copy and mark sent",
  agree: "Agree",
  follow_up: "Copy and mark sent",
  chase_post: "Copy and mark sent",
  mark_live: "Move to Live",
  mark_paid: "Mark paid",
  mark_lost: "Mark lost",
};
