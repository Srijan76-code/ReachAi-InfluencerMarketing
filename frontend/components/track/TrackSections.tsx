"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import NumberFlow from "@number-flow/react";
import { Check, ChevronDown, Copy, ExternalLink, Loader2, MessageSquare, MoreHorizontal, Upload } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { EvilAreaChart } from "@/components/evilcharts/charts/recharts-area-chart";
import { type ChartConfig } from "@/components/evilcharts/ui/recharts-chart";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { btn, btnPrimary, control, textarea } from "@/lib/ui";
import { DELIVERABLES, money } from "@/data/deals";
import { GOAL_KINDS, PAY_METHODS, type Track, type TrackCreator, type TrackPost } from "@/data/track";

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

export function SectionTitle({ children, aside }: { children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-3 px-1">
      <h2 className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">{children}</h2>
      {aside}
    </div>
  );
}

const sparkConfig = { views: { label: "Views", colors: { light: ["#18181b"], dark: ["#e4e4e7"] } } } satisfies ChartConfig;

/** One post: thumbnail, status, views with a small trend, and what the audience said. */
function PostCard({ p, api, campaignId, onChanged }: { p: TrackPost; api: Api; campaignId: string; onChanged: () => void }) {
  const [link, setLink] = useState("");
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cs = p.comment_summary;
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/posts/${p.id}/link`, { method: "POST", data: { url: link.trim() } });
      setAdding(false);
      onChanged();
    } catch (e) {
      setError(errorText(e, "Couldn't save the link"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <motion.li layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] overflow-hidden flex flex-col">
      <div className="relative aspect-video bg-zinc-100 dark:bg-[#141517]">
        {p.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- YouTube thumbnails, any size
          <img src={p.thumbnail_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-xs text-zinc-500">
            <CreatorAvatar name={p.name} src={p.avatar_url} className="w-9 h-9 rounded-full bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center" textClassName="text-xs font-medium" />
            {p.state === "late" ? "Not posted yet" : `Due ${p.due_on ? day(p.due_on) : "soon"}`}
          </div>
        )}
        <span className={`absolute top-2 left-2 text-[10px] font-medium px-2 py-0.5 rounded-full backdrop-blur
          ${p.state === "live" ? "bg-emerald-500/90 text-white" : p.state === "late" ? "bg-rose-500/90 text-white" : "bg-white/80 text-zinc-700 dark:bg-black/60 dark:text-zinc-200"}`}>
          {p.state === "live" ? `Live ${p.live_at ? ago(p.live_at) : ""}` : p.state === "late" ? `Late, due ${p.due_on ? day(p.due_on) : ""}` : `Due ${p.due_on ? day(p.due_on) : ""}`}
        </span>
      </div>
      <div className="p-3 space-y-2 flex-1 flex flex-col">
        <div className="flex items-center gap-2 min-w-0">
          <CreatorAvatar name={p.name} src={p.avatar_url} className="w-5 h-5 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center shrink-0" textClassName="text-[9px] font-medium" />
          <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100 truncate">{p.name}</p>
          <span className="text-[11px] text-zinc-500 shrink-0">· {kindLabel(p.deliverable)}</span>
        </div>
        {p.title && <p className="text-[11px] text-zinc-500 line-clamp-2" title={p.title}>{p.title}</p>}
        {p.state === "live" ? (
          <div className="flex items-end justify-between gap-2">
            <div>
              <p className="text-[18px] font-medium text-zinc-900 dark:text-zinc-100 leading-none"><NumberFlow value={p.views ?? 0} format={{ notation: "compact" }} /></p>
              <p className="text-[10px] text-zinc-500 mt-1">views{p.likes != null ? ` · ${n(p.likes)} likes` : ""}{p.comments != null ? ` · ${n(p.comments)} comments` : ""}</p>
            </div>
            {p.spark.length > 1 && (
              <div className="w-24 h-10 -mb-1">
                <EvilAreaChart data={p.spark} config={sparkConfig} className="h-full w-full" animationType="left-to-right">
                  <EvilAreaChart.Area dataKey="views" variant="gradient" strokeVariant="solid" strokeWidth={1.2} />
                </EvilAreaChart>
              </div>
            )}
          </div>
        ) : adding ? (
          <div className="flex gap-1.5">
            <input autoFocus value={link} onChange={(e) => setLink(e.target.value)} onKeyDown={(e) => e.key === "Enter" && link.trim() && save()}
              placeholder="youtube.com/watch?v=…" aria-label="Link to the post" className={control} />
            <button type="button" onClick={save} disabled={busy || !link.trim()} className={btnPrimary}>{busy ? <Loader2 size={12} className="animate-spin" /> : "Save"}</button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {p.state === "late" && <Link href={`/campaign/${campaignId}/outreach?chat=${p.deal_id}`} className={btn}><MessageSquare size={12} /> Remind them</Link>}
            <button type="button" onClick={() => setAdding(true)} className={btn}>Add link</button>
          </div>
        )}
        {error && <p className="text-[11px] text-rose-500">{error}</p>}
        {cs && !cs.disabled && cs.count ? (
          <div className="mt-auto pt-2 border-t border-zinc-100 dark:border-zinc-800/70 space-y-1.5">
            <div className="flex flex-wrap gap-1">
              <Chip tone={/positive/i.test(cs.sentiment ?? "") ? "good" : /negative/i.test(cs.sentiment ?? "") ? "bad" : "plain"}>{cs.sentiment}</Chip>
              {cs.product_interest && <Chip tone="good">Interest in your product</Chip>}
              {cs.product_questions && <Chip>Questions about it</Chip>}
              {cs.ad_backlash && <Chip tone="bad">Complaints about the ad</Chip>}
            </div>
            {cs.top?.[0] && <p className="text-[11px] text-zinc-500 italic line-clamp-2">&ldquo;{cs.top[0]}&rdquo;</p>}
          </div>
        ) : p.state === "live" ? (
          <p className="mt-auto pt-2 text-[10px] text-zinc-400">{cs?.disabled ? "Comments are off on this video." : "ReachAI reads the comments 3 days after it's live."}</p>
        ) : null}
        {p.url && (
          <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 inline-flex items-center gap-1">
            Watch <ExternalLink size={10} /> {p.found_by && p.found_by !== "you" && <span className="text-zinc-400">· found by {p.found_by === "jev" ? "ReachAI" : `their ${p.found_by}`}</span>}
          </a>
        )}
      </div>
    </motion.li>
  );
}

function Chip({ children, tone = "plain" }: { children: React.ReactNode; tone?: "good" | "bad" | "plain" }) {
  const c = tone === "good" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : tone === "bad" ? "bg-rose-500/10 text-rose-600 dark:text-rose-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300";
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${c}`}>{children}</span>;
}

export function Posts({ track, api, campaignId, onChanged }: { track: Track; api: Api; campaignId: string; onChanged: () => void }) {
  if (!track.posts.length) return null;
  const live = track.posts.filter((p) => p.state === "live").length;
  return (
    <section className="space-y-3">
      <SectionTitle aside={<span className="text-[11px] text-zinc-500">{live} of {track.posts.length} live</span>}>Posts</SectionTitle>
      <ul className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {track.posts.map((p) => <PostCard key={p.id} p={p} api={api} campaignId={campaignId} onChanged={onChanged} />)}
      </ul>
    </section>
  );
}

const VERDICT: Record<TrackCreator["verdict"], { label: string; cls: string }> = {
  rebook: { label: "Rebook", cls: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" },
  ok: { label: "OK", cls: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300" },
  skip: { label: "Skip next time", cls: "bg-rose-500/10 text-rose-600 dark:text-rose-400" },
  too_early: { label: "Too early", cls: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400" },
};

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

export function Creators({ track, api, onChanged }: { track: Track; api: Api; onChanged: () => void }) {
  const [counting, setCounting] = useState<TrackCreator | null>(null);
  const one = GOAL_KINDS.find((g) => g.value === track.goal.kind)?.one ?? "result";
  const resultsCol = track.goal.kind === "views" || track.goal.kind === "clicks" ? null : GOAL_KINDS.find((g) => g.value === track.goal.kind)?.label;
  if (!track.creators.length) return null;
  return (
    <section className="space-y-3">
      <SectionTitle aside={<span className="text-[11px] text-zinc-500">Best value first</span>}>Creators</SectionTitle>
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] overflow-x-auto">
        <table className="w-full text-xs min-w-[640px]">
          <thead>
            <tr className="text-[11px] text-zinc-500 text-left border-b border-zinc-200/70 dark:border-zinc-800/70">
              <th className="font-normal px-4 py-2.5">Creator</th>
              <th className="font-normal px-3 py-2.5 text-right">Cost</th>
              <th className="font-normal px-3 py-2.5 text-right">Views</th>
              <th className="font-normal px-3 py-2.5 text-right">Clicks</th>
              {resultsCol && <th className="font-normal px-3 py-2.5 text-right">{resultsCol}</th>}
              <th className="font-normal px-3 py-2.5 text-right">Per {one}</th>
              <th className="font-normal px-3 py-2.5 w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200/60 dark:divide-zinc-800/60">
            {track.creators.map((c, i) => (
              <motion.tr key={c.deal_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }}>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <CreatorAvatar name={c.name} src={c.avatar_url} className="w-7 h-7 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center shrink-0" textClassName="text-[10px] font-medium" />
                    <div className="min-w-0">
                      <p className="font-medium text-zinc-900 dark:text-zinc-100 truncate">{c.name}</p>
                      <p className="text-[10px] text-zinc-500 truncate" title={c.why}>
                        <span className={`inline-block mr-1.5 px-1.5 py-px rounded-full text-[10px] font-medium ${VERDICT[c.verdict].cls}`}>{VERDICT[c.verdict].label}</span>
                        {c.why}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-2.5 text-right font-mono">{money(c.cost)}</td>
                <td className="px-3 py-2.5 text-right font-mono">{n(c.views)}{c.expected_views ? <span className="block text-[10px] text-zinc-400 font-sans">of ~{n(c.expected_views)} expected</span> : null}</td>
                <td className="px-3 py-2.5 text-right font-mono">{n(c.clicks)}</td>
                {resultsCol && <td className="px-3 py-2.5 text-right font-mono">{n(c.results)}</td>}
                <td className="px-3 py-2.5 text-right font-mono">
                  {track.goal.kind === "views" ? (c.cost_per_1k_views != null ? `${money(c.cost_per_1k_views)}/1k` : "—") : c.cost_per_result != null ? `$${c.cost_per_result.toFixed(2)}` : "—"}
                </td>
                <td className="px-2 py-2.5">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button type="button" aria-label={`More for ${c.name}`} className="h-7 w-7 flex items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"><MoreHorizontal size={14} /></button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-52 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
                      <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => setCounting(c)}>Add signups or code uses</DropdownMenuItem>
                      {c.link && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => navigator.clipboard.writeText(c.link!.url)}>Copy their link</DropdownMenuItem>}
                      {c.code && <DropdownMenuItem className="text-xs cursor-pointer" onSelect={() => navigator.clipboard.writeText(c.code!)}>Copy their code ({c.code})</DropdownMenuItem>}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      {counting && <CountDialog c={counting} api={api} open onOpenChange={(v) => !v && setCounting(null)} onDone={onChanged} />}
    </section>
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

export function Payments({ track, api, onChanged }: { track: Track; api: Api; onChanged: () => void }) {
  const [paying, setPaying] = useState<Track["to_pay"][number] | null>(null);
  const [showPaid, setShowPaid] = useState(false);
  if (!track.to_pay.length && !track.paid.length) return null;
  const method = (m: string | null) => PAY_METHODS.find(([v]) => v === m)?.[1] ?? "";
  return (
    <section className="space-y-3">
      <SectionTitle aside={<span className="text-[11px] text-zinc-500">{money(track.totals.paid)} paid of {money(track.totals.spent)}</span>}>To pay</SectionTitle>
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] divide-y divide-zinc-200/60 dark:divide-zinc-800/60">
        <AnimatePresence initial={false}>
          {track.to_pay.map((p) => (
            <motion.div key={p.deal_id} layout exit={{ opacity: 0, height: 0 }} className="px-4 py-3 flex items-center gap-3">
              <CreatorAvatar name={p.name} src={p.avatar_url} className="w-7 h-7 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center shrink-0" textClassName="text-[10px] font-medium" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100 truncate">{p.name} <span className="font-mono">{money(p.amount)}</span></p>
                <p className="text-[11px] text-zinc-500">{p.why}</p>
              </div>
              <button type="button" onClick={() => setPaying(p)} className={btnPrimary}><Check size={12} /> Mark paid</button>
            </motion.div>
          ))}
        </AnimatePresence>
        {!track.to_pay.length && <p className="px-4 py-3 text-xs text-zinc-500">Nothing to pay right now.</p>}
        {track.paid.length > 0 && (
          <div className="px-4 py-2.5">
            <button type="button" onClick={() => setShowPaid((v) => !v)} className="text-[11px] text-zinc-500 flex items-center gap-1">
              Paid {track.paid.length} <ChevronDown size={11} className={`transition-transform ${showPaid ? "rotate-180" : ""}`} />
            </button>
            {showPaid && (
              <ul className="mt-2 space-y-1.5">
                {track.paid.map((p) => (
                  <li key={p.deal_id} className="text-xs flex items-center justify-between gap-2">
                    <span className="text-zinc-700 dark:text-zinc-300 truncate">{p.name}</span>
                    <span className="text-zinc-500 shrink-0"><span className="font-mono text-zinc-900 dark:text-zinc-100">{money(p.amount)}</span>{p.paid_at ? ` · ${day(p.paid_at)}` : ""}{p.method ? ` · ${method(p.method)}` : ""}
                      <button type="button" onClick={async () => { await api(`/api/deals/${p.deal_id}/unpaid`, { method: "POST" }); onChanged(); }} className="ml-2 underline underline-offset-2">Undo</button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      {paying && <PayDialog who={paying} api={api} open onOpenChange={(v) => !v && setPaying(null)} onDone={onChanged} />}
    </section>
  );
}

/** How results get counted: links (automatic), the signup snippet, and code uses from a store export. */
export function Setup({ track, api, campaignId, onChanged }: { track: Track; api: Api; campaignId: string; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [csv, setCsv] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const tag = `<script src="${track.snippet.src}" data-key="${track.snippet.key}" async></script>`;
  const thanks = `<script src="${track.snippet.src}" data-key="${track.snippet.key}" data-signup async></script>`;
  const copy = async () => {
    await navigator.clipboard.writeText(`<!-- On every page -->\n${tag}\n\n<!-- On your thank-you page, instead -->\n${thanks}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const upload = async () => {
    setBusy(true);
    setNote(null);
    try {
      const r = (await api(`/api/campaigns/${campaignId}/conversions/csv`, { method: "POST", data: { text: csv, kind: "code_use" } })).data as { added: number; unknown_codes: string[] };
      setNote(`Added ${r.added} code uses.${r.unknown_codes.length ? ` Not ours: ${r.unknown_codes.join(", ")}` : ""}`);
      setCsv("");
      onChanged();
    } catch (e) {
      setNote(errorText(e, "Couldn't read that"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800">
      <button type="button" onClick={() => setOpen((v) => !v)} className="w-full px-4 py-3 flex items-center justify-between text-left">
        <span>
          <span className="block text-[13px] font-medium text-zinc-900 dark:text-zinc-100">How results are counted</span>
          <span className="block text-[11px] text-zinc-500">Clicks on their links count by themselves. Add the snippet to count signups, or upload code uses.</span>
        </span>
        <ChevronDown size={14} className={`text-zinc-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="px-4 pb-4 grid gap-5 md:grid-cols-2">
              <div className="space-y-2">
                <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100">Count signups on your site</p>
                <p className="text-[11px] text-zinc-500">Add the first line to every page and the second to the page people see after signing up. When someone arrives from a creator&apos;s link and signs up, that creator gets the signup. Only their code is sent; nothing about the person.</p>
                <pre className="text-[10px] leading-relaxed bg-zinc-50 dark:bg-[#121314] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all text-zinc-700 dark:text-zinc-300">{tag}{"\n"}{thanks}</pre>
                <button type="button" onClick={copy} className={btn}>{copied ? <Check size={12} /> : <Copy size={12} />} {copied ? "Copied" : "Copy both"}</button>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100">Code uses from your store</p>
                <p className="text-[11px] text-zinc-500">Paste a CSV with the code and how many times it was used, one per line (Shopify, Stripe and most stores can export this).</p>
                <textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={4} placeholder={"code,uses\nSRIJAN42,12"} aria-label="Code uses CSV" className={`${textarea} font-mono`} />
                <div className="flex items-center gap-2">
                  <button type="button" onClick={upload} disabled={busy || !csv.trim()} className={btn}>{busy ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />} Add code uses</button>
                  {note && <span className="text-[11px] text-zinc-500">{note}</span>}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
