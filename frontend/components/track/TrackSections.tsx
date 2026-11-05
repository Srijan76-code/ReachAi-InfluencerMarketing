"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import NumberFlow from "@number-flow/react";
import { AlertCircle, Check, ChevronDown, ExternalLink, Flame, Loader2, MessageSquare, MoreHorizontal, Play, TrendingDown, TrendingUp } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { EvilAreaChart } from "@/components/evilcharts/charts/recharts-area-chart";
import { type ChartConfig } from "@/components/evilcharts/ui/recharts-chart";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { Select } from "@/components/ui/select";
import { btn, btnPrimary, control } from "@/lib/ui";
import { DELIVERABLES, money } from "@/data/deals";
import { GOAL_KINDS, type Insight, PAY_METHODS, type Track, type TrackCreator, type TrackPost } from "@/data/track";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

export const n = (v: number | null | undefined) => (v == null ? "—" : v >= 10000 ? `${(v / 1000).toFixed(v >= 100000 ? 0 : 1)}k` : v.toLocaleString());
const day = (iso: string) => new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const ago = (iso: string) => {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 864e5);
  return d <= 0 ? "today" : d === 1 ? "1 day ago" : `${d} days ago`;
};
export function errorText(e: unknown, fallback: string) {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof d === "string" ? d.replace(/\.$/, "") : fallback;
}
const kindLabel = (k: string) => DELIVERABLES.find(([v]) => v === k)?.[1] ?? k;
const avatar = "rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center shrink-0";

function Chip({ children, tone = "plain" }: { children: React.ReactNode; tone?: "good" | "bad" | "plain" | "hot" }) {
  const c = tone === "good" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : tone === "bad" ? "bg-rose-500/10 text-rose-600 dark:text-rose-400"
    : tone === "hot" ? "bg-orange-500/10 text-orange-600 dark:text-orange-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300";
  return <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full whitespace-nowrap ${c}`}>{children}</span>;
}

const TREND: Record<NonNullable<TrackPost["trend"]>, { tone: "good" | "bad" | "plain" | "hot"; icon: typeof Flame }> = {
  trending: { tone: "hot", icon: Flame },
  above: { tone: "good", icon: TrendingUp },
  usual: { tone: "plain", icon: TrendingUp },
  below: { tone: "bad", icon: TrendingDown },
};
const vsAvg = (x: number) => `${x}× avg`;
const MOOD: Record<string, string> = { "Very positive": "Very positive", "Mostly positive": "Positive", Mixed: "Mixed", "Mostly negative": "Negative", "Very negative": "Very negative" };

/* ---------------------------------------------------------------- insights (Overview) */

export function Insights({ items, campaignId, onSetup }: { items: Insight[]; campaignId: string; onSetup: () => void }) {
  if (!items.length) return null;
  return (
    <section className="space-y-2">
      <p className="px-1 text-[13px] font-medium text-zinc-900 dark:text-zinc-100">Highlights</p>
      <ul className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] divide-y divide-zinc-200/60 dark:divide-zinc-800/60">
        {items.map((i, k) => (
          <motion.li key={i.kind + k} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: k * 0.04 }} className="px-4 py-2.5 flex items-center gap-3 text-[13px]">
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${i.tone === "bad" ? "bg-rose-500" : i.tone === "good" ? "bg-emerald-500" : "bg-zinc-400"}`} />
            <span className="flex-1 text-zinc-700 dark:text-zinc-300">{i.text}</span>
            {i.action === "setup" && <button type="button" onClick={onSetup} className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">Set up</button>}
            {i.action === "remind" && <Link href={`/campaign/${campaignId}/track?tab=creators&filter=late`} className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">View</Link>}
          </motion.li>
        ))}
      </ul>
    </section>
  );
}

/* ---------------------------------------------------------------- dialogs */

/** Add signups, sales or code uses you counted yourself (from your store or dashboard). */
function CountDialog({ c, api, open, onOpenChange, onDone }: { c: TrackCreator; api: Api; open: boolean; onOpenChange: (v: boolean) => void; onDone: () => void }) {
  const [kind, setKind] = useState("signup");
  const [count, setCount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/deals/${c.deal_id}/conversions`, { method: "POST", data: { kind, count: Number(count) } });
      onOpenChange(false);
      onDone();
    } catch (e) {
      setError(errorText(e, "Couldn't add them"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm bg-white dark:bg-[#0c0d0e]">
        <DialogHeader>
          <DialogTitle className="text-[14px] font-medium">Add results for {c.name}</DialogTitle>
          <DialogDescription className="text-xs">What you counted yourself, from your store or dashboard. Use a negative number to correct.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <Field label="What"><Select label="What" value={kind} onChange={setKind} options={[{ value: "signup", label: "Signups" }, { value: "sale", label: "Sales" }, { value: "code_use", label: `Uses of ${c.code ?? "their code"}` }]} /></Field>
          <Field label="How many"><input value={count} onChange={(e) => setCount(e.target.value.replace(/[^\d-]/g, ""))} inputMode="numeric" placeholder="0" aria-label="How many" className={control} /></Field>
        </div>
        {error && <p className="text-[11px] text-rose-500">{error}</p>}
        <button type="button" onClick={save} disabled={busy || !count || count === "-"} className={btnPrimary}>{busy && <Loader2 size={12} className="animate-spin" />} Add</button>
      </DialogContent>
    </Dialog>
  );
}

/** Record a payment (ReachAI never moves money). */
function PayDialog({ who, api, open, onOpenChange, onDone }: { who: Track["to_pay"][number]; api: Api; open: boolean; onOpenChange: (v: boolean) => void; onDone: () => void }) {
  const [amount, setAmount] = useState(String(who.amount));
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [method, setMethod] = useState("paypal");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/deals/${who.deal_id}/paid`, { method: "POST", data: { amount: Number(amount), paid_on: date, method, note: note || null } });
      onOpenChange(false);
      onDone();
    } catch (e) {
      setError(errorText(e, "Couldn't save"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm bg-white dark:bg-[#0c0d0e]">
        <DialogHeader>
          <DialogTitle className="text-[14px] font-medium">Mark {who.name} paid</DialogTitle>
          <DialogDescription className="text-xs">Pay them the way you agreed, then record it here. ReachAI doesn&apos;t move money.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Amount">
            <span className="relative"><span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400">$</span>
              <input value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))} inputMode="decimal" aria-label="Amount" className={`${control} pl-6`} /></span>
          </Field>
          <Field label="Paid on"><input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Paid on" className={`${control} [color-scheme:light] dark:[color-scheme:dark]`} /></Field>
          <Field label="How" className="col-span-2"><Select label="How" value={method} onChange={setMethod} options={PAY_METHODS.map(([value, label]) => ({ value, label }))} /></Field>
          <Field label="Note (optional)" className="col-span-2"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reference or invoice number" aria-label="Note" className={control} /></Field>
        </div>
        {error && <p className="text-[11px] text-rose-500">{error}</p>}
        <button type="button" onClick={save} disabled={busy || !amount} className={btnPrimary}>{busy && <Loader2 size={12} className="animate-spin" />} Mark paid</button>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------------- Creators tab: results and payment in one row */

type CSort = "value" | "results" | "views" | "cost" | "pay";
type CFilter = "all" | "pay" | "late" | "rebook";
const VERDICT: Record<TrackCreator["verdict"], { label: string; tone: "good" | "bad" | "plain" }> = {
  rebook: { label: "Rebook", tone: "good" },
  ok: { label: "OK", tone: "plain" },
  skip: { label: "Skip next time", tone: "bad" },
  too_early: { label: "Too early", tone: "plain" },
};

function PostMini({ p }: { p: TrackPost }) {
  const t = p.trend ? TREND[p.trend] : null;
  return (
    <li className="flex items-center gap-3 py-2">
      <div className="w-16 aspect-video rounded-md overflow-hidden bg-zinc-100 dark:bg-[#141517] shrink-0">
        {/* eslint-disable-next-line @next/next/no-img-element -- YouTube thumbnails */}
        {p.thumbnail_url && <img src={p.thumbnail_url} alt="" className="w-full h-full object-cover" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-zinc-900 dark:text-zinc-100 truncate">{p.title ?? kindLabel(p.deliverable)}</p>
        <p className="text-[10px] text-zinc-500">{kindLabel(p.deliverable)} · {p.state === "live" ? `live ${p.live_at ? ago(p.live_at) : ""}` : p.state === "late" ? `late, due ${p.due_on ? day(p.due_on) : ""}` : `due ${p.due_on ? day(p.due_on) : "soon"}`}</p>
      </div>
      {p.state === "live" && (
        <div className="text-right shrink-0">
          <p className="text-xs font-mono text-zinc-900 dark:text-zinc-100">{n(p.views)}</p>
          {t && p.vs_usual != null && <Chip tone={t.tone}><t.icon size={9} /> {vsAvg(p.vs_usual)}</Chip>}
        </div>
      )}
      {p.url && <a href={p.url} target="_blank" rel="noopener noreferrer" aria-label="Watch" className="text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"><ExternalLink size={12} /></a>}
    </li>
  );
}

export function CreatorsTab({ track, api, campaignId, onChanged, initialFilter }: { track: Track; api: Api; campaignId: string; onChanged: () => void; initialFilter?: string }) {
  const [sort, setSort] = useState<CSort>("value");
  const [filter, setFilter] = useState<CFilter>((["pay", "late", "rebook"].includes(initialFilter ?? "") ? initialFilter : "all") as CFilter);
  const [open, setOpen] = useState<string | null>(null);
  const [counting, setCounting] = useState<TrackCreator | null>(null);
  const [paying, setPaying] = useState<TrackCreator | null>(null);
  const g = GOAL_KINDS.find((x) => x.value === track.goal.kind)!;
  const showResults = track.goal.kind === "signups" || track.goal.kind === "sales";
  const postsBy = useMemo(() => {
    const m = new Map<string, TrackPost[]>();
    for (const p of track.posts) m.set(p.deal_id, [...(m.get(p.deal_id) ?? []), p]);
    return m;
  }, [track.posts]);
  const counts = { pay: track.creators.filter((c) => c.to_pay).length, late: track.creators.filter((c) => c.late_posts).length, rebook: track.creators.filter((c) => c.verdict === "rebook").length };
  const rows = track.creators
    .filter((c) => filter === "all" || (filter === "pay" && c.to_pay) || (filter === "late" && c.late_posts) || (filter === "rebook" && c.verdict === "rebook"))
    .slice()
    .sort((a, b) => sort === "value" ? 0 : sort === "results" ? b.results - a.results : sort === "views" ? b.views - a.views : sort === "cost" ? b.cost - a.cost
      : (b.to_pay?.amount ?? -1) - (a.to_pay?.amount ?? -1));
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <Segmented label="Show" size="sm" value={filter} onChange={setFilter}
          options={[{ value: "all", label: "All", count: track.creators.length }, { value: "pay", label: "To pay", count: counts.pay || undefined },
            { value: "late", label: "Late", count: counts.late || undefined }, { value: "rebook", label: "Rebook", count: counts.rebook || undefined }]} />
        <div className="w-44"><Select label="Sort" value={sort} onChange={(v) => setSort(v as CSort)} options={[{ value: "value", label: "Best value first" },
          { value: "results", label: `Most ${g.label.toLowerCase()}` }, { value: "views", label: "Most views" }, { value: "cost", label: "Cost" }, { value: "pay", label: "To pay first" }]} /></div>
      </div>
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] divide-y divide-zinc-200/60 dark:divide-zinc-800/60">
        {rows.length > 0 && (
          <div className="hidden md:grid grid-cols-[minmax(0,1.6fr)_70px_80px_70px_90px_160px] gap-x-3 px-4 py-2 text-[11px] text-zinc-500">
            <span className="pl-[52px]">Creator</span><span className="text-right">Cost</span><span className="text-right">Views</span>
            <span className="text-right">{showResults ? g.label : "Clicks"}</span><span className="text-right">{track.goal.kind === "views" ? "CPM" : `Cost per ${g.one}`}</span>
            <span className="text-right pr-8">Payment</span>
          </div>
        )}
        {rows.length === 0 && <p className="px-4 py-10 text-center text-xs text-zinc-500">No creators</p>}
        <AnimatePresence initial={false}>
          {rows.map((c) => {
            const v = VERDICT[c.verdict];
            const expanded = open === c.deal_id;
            const posts = postsBy.get(c.deal_id) ?? [];
            return (
              <motion.div key={c.deal_id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="px-3 md:px-4 py-3 grid grid-cols-[minmax(0,1fr)_auto] md:grid-cols-[minmax(0,1.6fr)_70px_80px_70px_90px_160px] items-center gap-x-3 gap-y-2">
                  <button type="button" onClick={() => setOpen(expanded ? null : c.deal_id)} aria-expanded={expanded} className="flex items-center gap-2.5 min-w-0 text-left">
                    <ChevronDown size={13} className={`text-zinc-400 shrink-0 transition-transform ${expanded ? "" : "-rotate-90"}`} />
                    <CreatorAvatar name={c.name} src={c.avatar_url} className={`w-8 h-8 ${avatar}`} textClassName="text-[11px] font-medium" />
                    <span className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate">{c.name}</span>
                        <span title={c.why}><Chip tone={v.tone}>{v.label}</Chip></span>
                      </span>
                      <span className="block text-[11px] text-zinc-500 truncate">{c.live_posts}/{c.posts} live{c.late_posts ? ` · ${c.late_posts} late` : ""}</span>
                    </span>
                  </button>
                  <span className="hidden md:block text-right text-xs font-mono">{money(c.cost)}</span>
                  <span className="hidden md:block text-right text-xs font-mono">{n(c.views)}</span>
                  <span className="hidden md:block text-right text-xs font-mono">{showResults ? n(c.results) : n(c.clicks)}</span>
                  <span className="hidden md:block text-right text-xs font-mono">
                    {track.goal.kind === "views" ? (c.cost_per_1k_views != null ? `$${c.cost_per_1k_views.toFixed(2)}` : "—") : c.cost_per_result != null ? `$${c.cost_per_result.toFixed(2)}` : "—"}
                  </span>
                  <div className="flex items-center justify-end gap-1">
                    {c.paid ? (
                      <span className="text-[11px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 whitespace-nowrap"><Check size={12} /> Paid {money(c.paid_amount)}</span>
                    ) : c.to_pay ? (
                      <button type="button" onClick={() => setPaying(c)} className={btnPrimary} title={c.to_pay.why}>Pay {money(c.to_pay.amount)}</button>
                    ) : c.late_posts ? (
                      <Link href={`/campaign/${campaignId}/outreach?chat=${c.deal_id}`} className={btn}><MessageSquare size={12} /> Remind</Link>
                    ) : (
                      <span className="text-[11px] text-zinc-400">—</span>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button type="button" aria-label={`More for ${c.name}`} className="h-7 w-7 flex items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"><MoreHorizontal size={14} /></button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-56 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
                        <DropdownMenuItem className="text-xs cursor-pointer" asChild><Link href={`/campaign/${campaignId}/outreach?chat=${c.deal_id}`}>Open the chat</Link></DropdownMenuItem>
                        <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => setCounting(c)}>Add signups or code uses</DropdownMenuItem>
                        {!c.paid && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => setPaying(c)}>Mark paid</DropdownMenuItem>}
                        {c.paid && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={async () => { await api(`/api/deals/${c.deal_id}/unpaid`, { method: "POST" }); onChanged(); }}>Undo paid</DropdownMenuItem>}
                        {c.link && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => navigator.clipboard.writeText(c.link!.url)}>Copy their link</DropdownMenuItem>}
                        {c.code && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => navigator.clipboard.writeText(c.code!)}>Copy their code ({c.code})</DropdownMenuItem>}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  {/* phones: the numbers on their own line */}
                  <p className="md:hidden col-span-2 text-[11px] text-zinc-500 font-mono pl-[52px]">{money(c.cost)} · {n(c.views)} views · {showResults ? `${n(c.results)} ${g.label.toLowerCase()}` : `${n(c.clicks)} clicks`}</p>
                </div>
                <AnimatePresence initial={false}>
                  {expanded && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                      <div className="px-4 md:pl-[60px] pb-3">
                        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800/60">{posts.map((p) => <PostMini key={p.id} p={p} />)}</ul>
                        <p className="text-[11px] text-zinc-500 mt-1">
                          {c.clicks} clicks{c.conversions.signup ? ` · ${c.conversions.signup} signups` : ""}{c.conversions.sale ? ` · ${c.conversions.sale} sales` : ""}{c.conversions.code_use ? ` · ${c.conversions.code_use} code uses` : ""}
                          {c.code ? ` · code ${c.code}` : ""}
                          {c.paid && c.paid_at ? ` · paid ${day(c.paid_at)}${c.pay_method ? ` by ${PAY_METHODS.find(([k]) => k === c.pay_method)?.[1] ?? c.pay_method}` : ""}` : ""}
                        </p>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
      {counting && <CountDialog c={counting} api={api} open onOpenChange={(v) => !v && setCounting(null)} onDone={onChanged} />}
      {paying && <PayDialog who={{ deal_id: paying.deal_id, name: paying.name, avatar_url: paying.avatar_url, amount: paying.to_pay?.amount ?? paying.cost, why: "" }} api={api} open
        onOpenChange={(v) => !v && setPaying(null)} onDone={onChanged} />}
    </section>
  );
}

/* ---------------------------------------------------------------- Posts tab: a gallery with analysis on every card */

type PSort = "newest" | "views" | "usual" | "engagement" | "results";
const sparkConfig = { views: { label: "Views", colors: { light: ["#18181b"], dark: ["#e4e4e7"] } } } satisfies ChartConfig;

function Stat({ label, value, tone }: { label: string; value: string; tone?: "hot" | "bad" }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] text-zinc-500 truncate">{label}</p>
      <p className={`text-[13px] font-medium tabular-nums mt-0.5 ${tone === "hot" ? "text-orange-500" : tone === "bad" ? "text-rose-500" : "text-zinc-900 dark:text-zinc-100"}`}>{value}</p>
    </div>
  );
}

/** One post: the thumbnail carries the headline number; three named stats below; then what viewers say. */
function PostCard({ p, api, campaignId, goalLabel, onChanged }: { p: TrackPost; api: Api; campaignId: string; goalLabel: string | null; onChanged: () => void }) {
  const [link, setLink] = useState("");
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cs = p.comment_summary;
  const live = p.state === "live";
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/posts/${p.id}/link`, { method: "POST", data: { url: link.trim() } });
      setAdding(false);
      onChanged();
    } catch (e) {
      setError(errorText(e, "Not a YouTube link"));
    } finally {
      setBusy(false);
    }
  };
  const viewers = cs && !cs.disabled && cs.count
    ? [MOOD[cs.sentiment ?? ""] ?? cs.sentiment, cs.product_interest && "want the product", cs.product_questions && "asking about it", cs.ad_backlash && "disliked the ad"].filter(Boolean).join(" · ")
    : null;
  return (
    <motion.li layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }} whileHover={{ y: -2 }}
      transition={{ type: "spring", stiffness: 320, damping: 30 }}
      className="group rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] overflow-hidden flex flex-col hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors">
      {/* thumbnail with the headline number */}
      <a href={p.url ?? undefined} target={p.url ? "_blank" : undefined} rel="noopener noreferrer" className="relative block aspect-video bg-zinc-100 dark:bg-[#141517] overflow-hidden">
        {p.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- YouTube thumbnails
          <img src={p.thumbnail_url} alt="" className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.04]" />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <CreatorAvatar name={p.name} src={p.avatar_url} className={`w-10 h-10 ${avatar}`} textClassName="text-xs font-medium" />
          </div>
        )}
        {live && (
          <>
            <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black/75 via-black/25 to-transparent" />
            <div className="absolute left-3 bottom-2.5 text-white">
              <div className="text-[22px] font-semibold leading-none tabular-nums"><NumberFlow value={p.views ?? 0} format={{ notation: "compact" }} /></div>
              <p className="text-[10px] text-white/70 mt-1">views</p>
            </div>
            {p.spark.length > 1 && (
              <div className="absolute right-2 bottom-2 w-20 h-8 opacity-90">
                <EvilAreaChart data={p.spark} config={sparkConfig} className="h-full w-full" animationType="left-to-right">
                  <EvilAreaChart.Area dataKey="views" variant="gradient" strokeVariant="solid" strokeWidth={1.4} />
                </EvilAreaChart>
              </div>
            )}
            <span className="absolute inset-0 m-auto w-10 h-10 rounded-full bg-black/50 backdrop-blur flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <Play size={16} className="text-white ml-0.5" fill="white" />
            </span>
          </>
        )}
        <span className={`absolute top-2 left-2 text-[10px] font-medium px-2 py-0.5 rounded-full backdrop-blur
          ${live ? "bg-black/55 text-white" : p.state === "late" ? "bg-rose-500/90 text-white" : "bg-white/85 text-zinc-700 dark:bg-black/60 dark:text-zinc-200"}`}>
          {live ? (p.live_at ? ago(p.live_at) : "Live") : p.state === "late" ? `Late · due ${p.due_on ? day(p.due_on) : ""}` : `Due ${p.due_on ? day(p.due_on) : ""}`}
        </span>
        {p.trend === "trending" && p.vs_usual != null && (
          <span className="absolute top-2 right-2 text-[10px] font-medium px-2 py-0.5 rounded-full bg-orange-500 text-white flex items-center gap-1"><Flame size={10} /> {vsAvg(p.vs_usual)}</span>
        )}
      </a>

      <div className="p-3 flex-1 flex flex-col gap-2.5">
        <div className="min-w-0">
          {p.title && <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 line-clamp-2 leading-snug" title={p.title}>{p.title}</p>}
          <div className="text-[11px] text-zinc-500 flex items-center gap-1.5 mt-1 min-w-0">
            <CreatorAvatar name={p.name} src={p.avatar_url} className={`w-4 h-4 ${avatar}`} textClassName="text-[8px] font-medium" />
            <span className="truncate">{p.name}</span><span className="shrink-0">· {kindLabel(p.deliverable)}</span>
          </div>
        </div>

        {live ? (
          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-100 dark:border-zinc-800/70">
            <Stat label="Views / day" value={n(p.views_per_day)} />
            <Stat label="vs channel avg" value={p.vs_usual != null ? `${p.vs_usual}×` : "—"} tone={p.trend === "trending" ? "hot" : p.trend === "below" ? "bad" : undefined} />
            {goalLabel ? <Stat label={goalLabel} value={p.results != null ? n(p.results) : "—"} /> : <Stat label="Engagement" value={p.engagement != null ? `${p.engagement}%` : "—"} />}
          </div>
        ) : adding ? (
          <div className="flex gap-1.5">
            <input autoFocus value={link} onChange={(e) => setLink(e.target.value)} onKeyDown={(e) => e.key === "Enter" && link.trim() && save()}
              placeholder="youtube.com/watch?v=…" aria-label="Video link" className={control} />
            <button type="button" onClick={save} disabled={busy || !link.trim()} className={btnPrimary}>{busy ? <Loader2 size={12} className="animate-spin" /> : "Save"}</button>
          </div>
        ) : (
          <div className="flex gap-1.5">
            {p.state === "late" && <Link href={`/campaign/${campaignId}/outreach?chat=${p.deal_id}`} className={btn}><MessageSquare size={12} /> Remind</Link>}
            <button type="button" onClick={() => setAdding(true)} className={btn}>Add link</button>
          </div>
        )}
        {error && <p className="text-[11px] text-rose-500 flex items-center gap-1"><AlertCircle size={11} /> {error}</p>}

        {live && goalLabel && p.engagement != null && <p className="text-[11px] text-zinc-500 -mt-1">{p.engagement}% engagement</p>}
        {viewers && (
          <div className="mt-auto rounded-lg bg-zinc-50 dark:bg-[#121314] px-2.5 py-2">
            <p className="text-[11px] text-zinc-700 dark:text-zinc-300"><span className="text-zinc-500">Viewers:</span> {viewers}</p>
            {cs?.top?.[0] && <p className="text-[11px] text-zinc-500 italic line-clamp-1 mt-0.5" title={cs.top[0]}>&ldquo;{cs.top[0]}&rdquo;</p>}
          </div>
        )}
      </div>
    </motion.li>
  );
}

export function PostsTab({ track, api, campaignId, onChanged }: { track: Track; api: Api; campaignId: string; onChanged: () => void }) {
  const [sort, setSort] = useState<PSort>("newest");
  const [state, setState] = useState<"all" | "live" | "due" | "late">("all");
  const [who, setWho] = useState("all");
  const [format, setFormat] = useState("all");
  const formats = [...new Set(track.posts.map((p) => p.deliverable))];
  const goalLabel = track.goal.kind === "signups" ? "Signups" : track.goal.kind === "sales" ? "Sales" : null;
  const count = (s: string) => track.posts.filter((p) => p.state === s).length;
  const shown = track.posts
    .filter((p) => (state === "all" || p.state === state) && (who === "all" || p.deal_id === who) && (format === "all" || p.deliverable === format))
    .slice()
    .sort((a, b) => {
      const v = (x: number | null | undefined) => x ?? -1;
      if (sort === "views") return v(b.views) - v(a.views);
      if (sort === "usual") return v(b.vs_usual) - v(a.vs_usual);
      if (sort === "engagement") return v(b.engagement) - v(a.engagement);
      if (sort === "results") return v(b.results) - v(a.results);
      const rank = { live: 0, late: 1, due: 2 } as const; // live first (newest), then late, then what's due soonest
      if (rank[a.state] !== rank[b.state]) return rank[a.state] - rank[b.state];
      return a.state === "live" ? (b.live_at ?? "").localeCompare(a.live_at ?? "") : (a.due_on ?? "").localeCompare(b.due_on ?? "");
    });
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <Segmented label="Status" size="sm" value={state} onChange={setState}
          options={[{ value: "all", label: "All", count: track.posts.length }, { value: "live", label: "Live", count: count("live") || undefined },
            { value: "due", label: "Due", count: count("due") || undefined }, { value: "late", label: "Late", count: count("late") || undefined }]} />
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-40"><Select label="Creator" value={who} onChange={setWho} options={[{ value: "all", label: "All creators" }, ...track.creators.map((c) => ({ value: c.deal_id, label: c.name }))]} /></div>
          {formats.length > 1 && <div className="w-40"><Select label="Format" value={format} onChange={setFormat} options={[{ value: "all", label: "All formats" }, ...formats.map((f) => ({ value: f, label: kindLabel(f) }))]} /></div>}
          <div className="w-44"><Select label="Sort" value={sort} onChange={(v) => setSort(v as PSort)} options={[{ value: "newest", label: "Newest" }, { value: "views", label: "Views" },
            { value: "usual", label: "vs channel avg" }, { value: "engagement", label: "Engagement" }, { value: "results", label: goalLabel ?? "Signups" }]} /></div>
        </div>
      </div>
      {shown.length === 0 ? (
        <p className="rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800 py-12 text-center text-xs text-zinc-500">No posts</p>
      ) : (
        <ul className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <AnimatePresence initial={false}>{shown.map((p) => <PostCard key={p.id} p={p} api={api} campaignId={campaignId} onChanged={onChanged} goalLabel={goalLabel} />)}</AnimatePresence>
        </ul>
      )}
    </section>
  );
}
