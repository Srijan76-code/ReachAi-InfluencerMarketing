"use client";

import { BACKEND_URL } from "@/lib/backend";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "motion/react";
import NumberFlow from "@number-flow/react";
import { CheckCircle2, Download, Loader2, Pencil, Plug, RefreshCw, TrendingUp } from "lucide-react";
import { EvilAreaChart } from "@/components/evilcharts/charts/recharts-area-chart";
import { type ChartConfig } from "@/components/evilcharts/ui/recharts-chart";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Segmented } from "@/components/ui/segmented";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useApi } from "@/lib/api";
import { btn, btnPrimary, control } from "@/lib/ui";
import { money } from "@/data/deals";
import { GOAL_KINDS, type GoalKind, type Track } from "@/data/track";
import { CreatorsTab, Insights, PostsTab, errorText } from "@/components/track/TrackSections";
import { SetupSheet } from "@/components/track/SetupSheet";
import { updatedLabel } from "@/types/campaign";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
type Metric = "results" | "views" | "clicks";
type Tab = "overview" | "creators" | "posts";

const chartConfig = {
  results: { label: "Results", colors: { light: ["#2563eb"], dark: ["#60a5fa"] } },
  views: { label: "Views", colors: { light: ["#18181b"], dark: ["#e4e4e7"] } },
  clicks: { label: "Clicks", colors: { light: ["#059669"], dark: ["#34d399"] } },
} satisfies ChartConfig;

/** The goal: how many, of what, and what each is worth to you (for return on spend). */
function GoalEditor({ track, api, campaignId, onSaved }: { track: Track; api: Api; campaignId: string; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<GoalKind>(track.goal.kind);
  const [count, setCount] = useState(track.goal.count ? String(track.goal.count) : "");
  const [value, setValue] = useState(track.goal.value_each != null ? String(track.goal.value_each) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/campaigns/${campaignId}/track`, { method: "PATCH", data: { goal_kind: kind, goal_count: count ? Number(count) : null, value_each: value ? Number(value) : null } });
      setOpen(false);
      onSaved();
    } catch (e) {
      setError(errorText(e, "Couldn't save"));
    } finally {
      setBusy(false);
    }
  };
  const valued = kind === "signups" || kind === "sales";
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" aria-label="Change the goal" className="h-7 w-7 rounded-md flex items-center justify-center text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800"><Pencil size={13} /></button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 space-y-3">
        <p className="text-[13px] font-medium">Your goal</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="How many"><input value={count} onChange={(e) => setCount(e.target.value.replace(/\D/g, ""))} inputMode="numeric" placeholder="500" aria-label="How many" className={control} /></Field>
          <Field label="Of"><Select label="Of" value={kind} onChange={(v) => setKind(v as GoalKind)} options={GOAL_KINDS.map((g) => ({ value: g.value, label: g.label }))} /></Field>
        </div>
        {valued && (
          <Field label={`What one ${GOAL_KINDS.find((g) => g.value === kind)?.one} is worth to you (optional)`} hint="Shows your return on what you paid creators.">
            <span className="relative"><span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400">$</span>
              <input value={value} onChange={(e) => setValue(e.target.value.replace(/[^\d.]/g, ""))} inputMode="decimal" placeholder="20" aria-label="Value" className={`${control} pl-6`} /></span>
          </Field>
        )}
        {error && <p className="text-[11px] text-rose-500">{error}</p>}
        <button type="button" onClick={save} disabled={busy} className={`${btnPrimary} w-full`}>{busy && <Loader2 size={12} className="animate-spin" />} Save</button>
      </PopoverContent>
    </Popover>
  );
}

function Tile({ label, value, sub, prefix, suffix, decimals = 0, delay = 0 }: { label: string; value: number | null; sub?: string; prefix?: string; suffix?: string; decimals?: number; delay?: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, type: "spring", stiffness: 300, damping: 30 }}
      className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] px-4 py-3.5">
      <p className="text-[11px] text-zinc-500">{label}</p>
      <div className="text-[22px] font-medium text-zinc-900 dark:text-zinc-100 mt-1 leading-none">
        {value == null ? "—" : <NumberFlow value={value} prefix={prefix} suffix={suffix} format={{ notation: value >= 100000 ? "compact" : "standard", maximumFractionDigits: decimals, minimumFractionDigits: decimals }} />}
      </div>
      {sub && <p className="text-[11px] text-zinc-500 mt-1.5 truncate">{sub}</p>}
    </motion.div>
  );
}

/** Track (spec §7.6): one page that answers "was it worth it?" Numbers come from YouTube, your links,
 * your site and what you enter; ReachAI checks for new posts and numbers every day. */
export default function TrackBoard({ campaignId, apiOverride }: { campaignId: string; apiOverride?: Api }) {
  const signedInApi = useApi();
  const api = apiOverride ?? signedInApi;
  const [track, setTrack] = useState<Track | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [metric, setMetric] = useState<Metric>("results");
  const [setupOpen, setSetupOpen] = useState(false);
  const router = useRouter();
  const params = useSearchParams();
  const tab = (["overview", "creators", "posts"].includes(params?.get("tab") ?? "") ? params!.get("tab") : "overview") as Tab;
  const setTab = (t: Tab) => {
    const p = new URLSearchParams(params?.toString() ?? "");
    if (t === "overview") p.delete("tab");
    else p.set("tab", t);
    p.delete("filter");
    router.replace(`?${p.toString()}`, { scroll: false });
  };

  const load = () =>
    api(`/api/campaigns/${campaignId}/track`)
      .then((r) => {
        setTrack(r.data as Track);
        setError(null);
      })
      .catch(() => setError("Couldn't load. Refresh to try again."));

  const check = async (force = false) => {
    setChecking(true);
    try {
      const r = (await api(`/api/campaigns/${campaignId}/track/refresh${force ? "?force=true" : ""}`, { method: "POST" })).data as { skipped?: boolean };
      if (!r.skipped) await load();
    } catch {
      // the daily check still runs; nothing to show
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    load().then(() => check());
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [campaignId]);

  if (error) return <p className="text-xs text-rose-500 px-1">{error}</p>;
  if (!track)
    return (
      <div className="space-y-4" aria-label="Loading">
        <div className="h-64 rounded-2xl bg-zinc-200/50 dark:bg-zinc-800/40 animate-pulse motion-reduce:animate-none" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <div key={i} className="h-20 rounded-xl bg-zinc-200/50 dark:bg-zinc-800/40 animate-pulse motion-reduce:animate-none" />)}</div>
      </div>
    );

  if (!track.creators.length)
    return (
      <div className="flex flex-col items-center justify-center text-center py-24 rounded-2xl border border-dashed border-zinc-200 dark:border-zinc-800">
        <TrendingUp size={22} className="text-zinc-400 mb-3" />
        <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">Nothing to track yet</p>
        <p className="text-xs text-zinc-500 mt-1 mb-4">Agreed creators show up here.</p>
        <Link href={`/campaign/${campaignId}/outreach`} className={btn}>Go to Outreach</Link>
      </div>
    );

  const t = track.totals;
  const g = GOAL_KINDS.find((x) => x.value === track.goal.kind)!;
  const pct = track.goal.count ? Math.min(100, (t.results / track.goal.count) * 100) : null;
  const paceTo = track.forecast ? (track.goal.kind === "views" ? track.forecast.views : track.forecast.results) : null;
  const hasData = track.series.some((d) => d[metric] > 0);

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-8 md:-mt-6">
        <div className="flex flex-wrap items-center justify-between gap-3 px-1">
          <div className="flex items-center gap-3">
            <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100">Track</h1>
            <Segmented label="Track view" value={tab} onChange={setTab}
              options={[{ value: "overview", label: "Overview" }, { value: "creators", label: "Creators", count: track.creators.length },
                { value: "posts", label: "Posts", count: track.posts.length }]} />
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setSetupOpen(true)} className={btn}>
              {track.snippet.seen_at ? <CheckCircle2 size={12} className="text-emerald-500" /> : <Plug size={12} />}
              <span className="hidden sm:inline">Count signups</span>
            </button>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" onClick={() => check(true)} disabled={checking} aria-label="Check for new posts" className={`${btn} !px-0 w-[30px]`}>
                  <RefreshCw size={13} className={`shrink-0 ${checking ? "animate-spin" : ""}`} />
                </button>
              </TooltipTrigger>
              <TooltipContent className="text-xs">{checking ? "Checking…" : track.refreshed_at ? `Updated ${updatedLabel(track.refreshed_at)}` : "Check for new posts"}</TooltipContent>
            </Tooltip>
            <a href={`${BACKEND_URL}/api/campaigns/${campaignId}/track.csv`} onClick={async (e) => {
              e.preventDefault(); // the download needs the sign-in token, so fetch it and save the file
              const r = await api(`/api/campaigns/${campaignId}/track.csv`, { responseType: "blob" });
              const url = URL.createObjectURL(r.data as Blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "results.csv";
              a.click();
              URL.revokeObjectURL(url);
            }} className={btn}><Download size={12} /> <span className="hidden sm:inline">Export</span></a>
          </div>
        </div>

        {tab === "overview" && <>
        {/* the goal, the pace, the last 30 days */}
        <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] overflow-hidden">
          <div className="px-5 md:px-6 pt-5 flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-1.5">
                <p className="text-[11px] text-zinc-500">{track.goal.count ? "Goal" : "So far"}</p>
                <GoalEditor key={JSON.stringify(track.goal)} track={track} api={api} campaignId={campaignId} onSaved={load} />
              </div>
              <div className="text-zinc-900 dark:text-zinc-100 flex items-baseline gap-2">
                <span className="text-[40px] font-medium leading-none tracking-tight"><NumberFlow value={t.results} format={{ notation: t.results >= 100000 ? "compact" : "standard" }} /></span>
                <span className="text-sm text-zinc-500">{track.goal.count ? `of ${track.goal.count.toLocaleString()} ${g.label.toLowerCase()}` : g.label.toLowerCase()}</span>
              </div>
              {paceTo != null && track.forecast?.by && (
                <p className="text-xs text-zinc-500 mt-2 flex items-center gap-1.5">
                  <TrendingUp size={12} className="text-blue-500" /> On pace for ~{paceTo.toLocaleString()} by {new Date(track.forecast.by + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  <span className="text-zinc-400">est.</span>
                </p>
              )}
              
            </div>
            <Segmented label="Chart" size="sm" value={metric} onChange={setMetric}
              options={[{ value: "results", label: track.goal.kind === "views" || track.goal.kind === "clicks" ? "Goal" : g.label }, { value: "views", label: "Views" }, { value: "clicks", label: "Clicks" }]} />
          </div>
          {pct != null && (
            <div className="px-5 md:px-6 mt-4">
              <div className="h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
                <motion.div className="h-full rounded-full bg-blue-500" initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 1, ease: [0.2, 0.8, 0.2, 1] }} />
              </div>
            </div>
          )}
          <div className="h-56 mt-2 relative">
            {hasData ? (
              <EvilAreaChart key={metric} data={track.series} config={chartConfig} className="h-full w-full px-2 pb-2" animationType="left-to-right" curveType="monotone">
                <EvilAreaChart.Grid />
                <EvilAreaChart.XAxis dataKey="day" tickFormatter={(v: string) => new Date(v + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" })} />
                <EvilAreaChart.Tooltip />
                <EvilAreaChart.Area dataKey={metric} variant="gradient" strokeVariant="solid" strokeWidth={1.6}>
                  <EvilAreaChart.ActiveDot variant="default" />
                </EvilAreaChart.Area>
              </EvilAreaChart>
            ) : (
              <p className="absolute inset-0 flex items-center justify-center text-xs text-zinc-500">No data yet</p>
            )}
          </div>
        </motion.section>

        {/* the four numbers */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Tile label="Spent" value={t.spent} prefix="$" sub={track.budget ? `of ${money(track.budget)}` : undefined} />
          <Tile label="Views" value={t.views} sub={t.cost_per_1k_views != null ? `$${t.cost_per_1k_views.toFixed(2)} CPM` : undefined} delay={0.05} />
          <Tile label="Clicks" value={t.clicks} sub={t.views ? `${((t.clicks / t.views) * 100).toFixed(2)}% CTR` : undefined} delay={0.1} />
          {t.return != null ? (
            <Tile label="ROI" value={t.return} suffix="×" decimals={1} sub={`${money(t.value)} value`} delay={0.15} />
          ) : (
            <Tile label={`Cost per ${track.goal.kind === "views" || track.goal.kind === "clicks" ? "signup" : g.one}`} value={t.cost_per_result} prefix="$" decimals={2}
              sub={t.code_uses ? `${t.code_uses} code uses` : undefined} delay={0.15} />
          )}
        </div>

        <Insights items={track.insights} campaignId={campaignId} onSetup={() => setSetupOpen(true)} />
        </>}
        {tab === "creators" && <CreatorsTab track={track} api={api} campaignId={campaignId} onChanged={load} initialFilter={params?.get("filter") ?? undefined} />}
        {tab === "posts" && <PostsTab track={track} api={api} campaignId={campaignId} onChanged={load} />}
        <SetupSheet open={setupOpen} onOpenChange={setSetupOpen} track={track} api={api} campaignId={campaignId} onChanged={load} />
      </div>
    </TooltipProvider>
  );
}
