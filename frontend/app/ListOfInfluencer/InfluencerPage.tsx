"use client";

import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { TooltipProvider } from "@/components/ui/tooltip";
import { InfluencerRow } from "./InfluencerRow";
import { useCampaignStore } from "@/store/campaignStore";
import { useApi } from "@/lib/api";
import { Loader2Icon } from "lucide-react";
import {
  ListFilter,
  ArrowUpDown,
  Download,
  ChevronDown,
  FileSpreadsheet,
  FileText,
  Send,
  Search,
  Keyboard,
  X,
  MoreHorizontal,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
} from "@/components/ui/dropdown-menu";
import { Sheet } from "@/components/ui/sheet";
import { LeadListSkeleton } from "@/components/LeadListSkeleton";
import { SkippedNote } from "@/components/SkippedNote";
import { ShareDialog } from "@/components/ShareDialog";
import { CompareTray, MAX_COMPARE } from "@/components/CompareTray";
import type { FeedbackItem } from "@/data/influencerList";
import {
  DEFAULT_VIEW,
  SORTS,
  activeFilterCount,
  applyView,
  parseView,
  platformCounts,
  type LeadView,
} from "@/lib/leadView";
import { InfluencerDetailSheet } from "./InfluencerDetailSheet";
import { ExportDialog } from "@/components/ExportDialog";
import { OutreachDialog } from "@/components/OutreachDialog";
import { CampaignSummaryBanner } from "./CampaignSummaryBanner";
import { motion, AnimatePresence } from "motion/react";
import { staggerItemVariants } from "@/components/animations/variants";

const PLATFORM_NAMES: Record<string, string> = {
  all: "All",
  youtube: "YouTube",
  instagram: "Instagram",
  x: "X",
  linkedin: "LinkedIn",
};

const SHORTCUTS: [string, string][] = [
  ["j / k", "Next / previous creator"],
  ["Enter", "Open creator"],
  ["s", "Save / unsave"],
  ["x", "Select"],
  ["/", "Search"],
  ["Esc", "Clear selection"],
  ["?", "Show shortcuts"],
];

interface InfluencerPageProps {
  campaignId?: string;
}

const InfluencerPage = ({ campaignId }: InfluencerPageProps) => {
  const api = useApi();
  const isGenerating = useCampaignStore((state) => state.isGenerating);
  const currentStage = useCampaignStore((state) => state.currentStage);
  const stageIndex = useCampaignStore((state) => state.stageIndex);
  const status = useCampaignStore((state) => state.status);
  const final_ranked_leads = useCampaignStore((state) => state.finalInfluencers);
  const savedLeadsMap = useCampaignStore((state) => state.savedLeadsMap);
  const loadCampaignFromCacheOrFetch = useCampaignStore((state) => state.loadCampaignFromCacheOrFetch);
  const fetchSavedLeads = useCampaignStore((state) => state.fetchSavedLeads);
  const toggleSaveLead = useCampaignStore((state) => state.toggleSaveLead);

  useEffect(() => {
    if (campaignId) {
      loadCampaignFromCacheOrFetch(campaignId, api);
      fetchSavedLeads(campaignId, api);
    }
  }, [campaignId]);

  // Sort, filters and search: one object, remembered per campaign in this browser
  const viewKey = `reachai:view:${campaignId ?? "local"}`;
  const [view, setView] = useState<LeadView>(DEFAULT_VIEW);
  const [viewLoaded, setViewLoaded] = useState(false);
  useEffect(() => {
    let raw: string | null = null;
    try {
      raw = window.localStorage.getItem(viewKey);
    } catch {}
    const restored = parseView(raw);
    // the old Saved page and shared links open straight on the shortlist
    const wantsShortlist = new URLSearchParams(window.location.search).get("view") === "shortlist";
    setView(wantsShortlist ? { ...restored, savedOnly: true } : restored);
    setViewLoaded(true);
  }, [viewKey]);
  useEffect(() => {
    if (!viewLoaded) return;
    try {
      window.localStorage.setItem(viewKey, JSON.stringify({ ...view, query: "" })); // search isn't remembered
    } catch {}
  }, [view, viewKey, viewLoaded]);
  const set = <K extends keyof LeadView>(k: K, v: LeadView[K]) => setView((prev) => ({ ...prev, [k]: v }));
  const filterCount = activeFilterCount(view);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [openId, setOpenId] = useState<string | null>(null); // creator whose panel is open
  const [cursor, setCursor] = useState<number | null>(null); // highlighted row
  const keyboardNav = useRef(false); // the highlight stays after closing a panel only when moving with j/k
  const [helpOpen, setHelpOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [feedback, setFeedback] = useState<Record<string, FeedbackItem[]>>({});
  // what reviewers said (share links with the Reviewer role); refreshed when the page opens
  useEffect(() => {
    if (!campaignId) return;
    let live = true;
    api(`/api/campaigns/${campaignId}/feedback`)
      .then((r) => {
        if (!live || !Array.isArray(r.data)) return;
        const by: Record<string, FeedbackItem[]> = {};
        for (const f of r.data as FeedbackItem[]) (by[f.creator_id] ||= []).push(f);
        setFeedback(by);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api is a new function each render
  }, [campaignId]);
  const searchRef = useRef<HTMLInputElement>(null);

  const displayedLeads = useMemo(
    () => applyView(final_ranked_leads, view, savedLeadsMap),
    [final_ranked_leads, view, savedLeadsMap],
  );
  const platforms = useMemo(() => platformCounts(final_ranked_leads ?? []), [final_ranked_leads]);
  const shortlistCount = useMemo(
    () => (final_ranked_leads ?? []).filter((l) => savedLeadsMap[l.id]).length,
    [final_ranked_leads, savedLeadsMap],
  );
  // what Start outreach and Export act on: the selected creators, else everyone in the current view
  const actionTargets = useMemo(
    () => (selectedIds.size > 0 ? displayedLeads.filter((l) => selectedIds.has(l.id)) : displayedLeads),
    [displayedLeads, selectedIds],
  );

  const saveError = useCampaignStore((state) => state.saveError);
  useEffect(() => {
    if (!saveError) return;
    const t = setTimeout(() => useCampaignStore.setState({ saveError: null }), 4000);
    return () => clearTimeout(t);
  }, [saveError]);

  // keep the highlight inside the list when filters shrink it
  useEffect(() => {
    if (cursor !== null && cursor >= displayedLeads.length) setCursor(displayedLeads.length ? displayedLeads.length - 1 : null);
  }, [displayedLeads.length, cursor]);

  function toggleSelection(id: string) {
    setSelectedIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) newSet.delete(id);
      else newSet.add(id);
      return newSet;
    });
  }

  const moveTo = useCallback((i: number) => {
    setCursor(i);
    document.querySelector(`[data-lead-index="${i}"]`)?.scrollIntoView({ block: "nearest" });
  }, []);

  // Keyboard: j/k or arrows move, Enter opens, s saves, x selects, / searches, Esc clears, ? shows help.
  // With a panel open, j/k step to the next/previous creator's panel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      const typing = !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
      if (typing) {
        if (e.key === "Escape" && t === searchRef.current) {
          if (view.query) set("query", "");
          else searchRef.current?.blur();
        }
        if (e.key === "Enter" && t === searchRef.current && displayedLeads.length) {
          searchRef.current?.blur();
          moveTo(0);
        }
        return;
      }
      // another dialog (outreach, export) is open: leave its keys alone
      if (!openId && document.querySelector('[role="dialog"], [role="menu"]')) return;
      const n = displayedLeads.length;
      const step = (d: number) => {
        e.preventDefault();
        if (!n) return;
        const from = openId ? displayedLeads.findIndex((l) => l.id === openId) : cursor;
        const next = from === null || from < 0 ? (d > 0 ? 0 : n - 1) : Math.min(n - 1, Math.max(0, from + d));
        keyboardNav.current = true;
        moveTo(next);
        if (openId) setOpenId(displayedLeads[next].id);
      };
      const current = cursor !== null ? displayedLeads[cursor] : undefined;
      switch (e.key) {
        case "j":
        case "ArrowDown":
          return step(1);
        case "k":
        case "ArrowUp":
          return step(-1);
      }
      if (openId) return; // the panel handles its own Escape
      switch (e.key) {
        case "Enter":
        case "o":
          if (current) {
            e.preventDefault();
            setOpenId(current.id);
          }
          return;
        case "s":
          if (current && campaignId) {
            e.preventDefault();
            toggleSaveLead(campaignId, current, api);
          }
          return;
        case "x":
          if (current) {
            e.preventDefault();
            toggleSelection(current.id);
          }
          return;
        case "/":
          e.preventDefault();
          searchRef.current?.focus();
          return;
        case "?":
          e.preventDefault();
          setHelpOpen((o) => !o);
          return;
        case "Escape":
          if (selectedIds.size) setSelectedIds(new Set());
          else setCursor(null);
          return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api/toggleSelection are recreated each render
  }, [displayedLeads, cursor, openId, selectedIds, campaignId, view.query, moveTo]);

  // if (isGenerating || status === "PENDING") {
  //   return (
  //     <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] flex flex-col items-center justify-center text-zinc-600 dark:text-zinc-400 p-8 font-sans">
  //       <Loader2Icon className="w-10 h-10 animate-spin text-blue-500 mb-6" />
  //       <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
  //         {stageIndex ? `Stage ${stageIndex}` : "Processing LangGraph Workflow"}
  //       </h2>
  //       <p className="mt-2 text-sm max-w-md text-center opacity-80 font-mono">
  //         {currentStage || "Our LangGraph AI agent is currently analyzing and discovering creators..."}
  //       </p>
  //     </div>
  //   );
  // }

  const isLoadingCampaign = useCampaignStore((state) => state.isLoadingCampaign);

  // Loading state while checking DB
  if (isLoadingCampaign && (!final_ranked_leads || final_ranked_leads.length === 0)) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] p-8">
        <div className="max-w-7xl mx-auto space-y-4">
          <div className="flex items-center px-1 py-3 mb-2">
            <div className="w-10" />
            <div className="h-4 w-32 rounded bg-zinc-200/70 dark:bg-zinc-800/70 animate-pulse motion-reduce:animate-none" />
          </div>
          <LeadListSkeleton />
        </div>
      </div>
    );
  }

  // Active generation in-progress
  if ((isGenerating || status === "PENDING") && (!final_ranked_leads || final_ranked_leads.length === 0)) {
    return (
      <div className="min-h-[50vh] bg-zinc-50 dark:bg-[#08090a] flex flex-col items-center justify-center text-zinc-600 dark:text-zinc-400 p-8">
        <Loader2Icon size={18} className="animate-spin text-blue-500 mb-3" />
        <p className="text-xs font-medium text-zinc-800 dark:text-zinc-200">
          Generating and ranking leads...
        </p>
        <p className="text-[11px] text-zinc-500 mt-1">
          Tracking discovery, verification, and scoring in real time above.
        </p>
      </div>
    );
  }

  // Fallback if accessed before generating
  if (!final_ranked_leads || final_ranked_leads.length === 0) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] flex flex-col items-center justify-center text-zinc-600 dark:text-zinc-400 p-8">
        <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 mb-4">No campaign leads generated yet.</p>
        {campaignId && (
          <Link
            href={`/campaign/${campaignId}/details`}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 hover:opacity-90 transition-opacity"
          >
            Configure Campaign Details
          </Link>
        )}
      </div>
    );
  }


  const toggleSelectAll = () => {
    if (
      selectedIds.size === displayedLeads.length &&
      displayedLeads.length > 0
    ) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(displayedLeads.map((l) => l.id)));
    }
  };

  return (
    // <StaggerFadeRise className="">
      <TooltipProvider delayDuration={150}>
        <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] text-zinc-600 dark:text-zinc-400 p-8 font-sans selection:bg-blue-500/30">
          <div className="max-w-7xl mx-auto space-y-4">
            {/* --- HEADER SECTION --- */}
            <motion.div variants={staggerItemVariants}  className="flex items-center justify-between px-1 py-3 mb-2">
              <div className="flex items-center">
                {/* Master Checkbox (w-10 precisely aligns with the row checkboxes below) */}
                <div
                  onClick={toggleSelectAll}
                  className="w-10 flex items-center justify-center cursor-pointer group"
                >
                  <div
                    className={`w-[13px] h-[13px] rounded-[3px] border flex items-center justify-center transition-colors group-hover:border-zinc-400 dark:group-hover:border-white/30 ${selectedIds.size > 0 ? "border-zinc-900 bg-zinc-900 dark:border-[#ededed] dark:bg-[#ededed]" : "border-zinc-300 dark:border-white/10 bg-white dark:bg-transparent"}`}
                  >
                    {selectedIds.size > 0 &&
                      selectedIds.size === displayedLeads.length && (
                        <svg
                          width="8"
                          height="6"
                          viewBox="0 0 9 7"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                          className="text-white dark:text-[#0a0a0a]"
                        >
                          <path
                            d="M1 3.5L3.5 6L8 1"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    {selectedIds.size > 0 &&
                      selectedIds.size !== displayedLeads.length && (
                        <div className="w-1.5 h-[1.5px] bg-white dark:text-black dark:bg-[#0a0a0a] rounded-full" />
                      )}
                  </div>
                </div>

                {/* Title, All | Shortlist, and how the list was made */}
                <div className="flex items-center gap-3 pl-1 min-w-0">
                  {selectedIds.size > 0 ? (
                    <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 whitespace-nowrap">
                      {selectedIds.size} selected
                    </span>
                  ) : (
                    <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100 tracking-tight">Creators</h1>
                  )}
                  <div role="tablist" aria-label="Which creators" className="flex items-center h-[30px] p-[3px] gap-0.5 rounded-md border border-zinc-200 dark:border-zinc-800 text-xs">
                    {([false, true] as const).map((only) => (
                      <button
                        key={String(only)}
                        role="tab"
                        type="button"
                        aria-selected={view.savedOnly === only}
                        onClick={() => set("savedOnly", only)}
                        className={`h-full px-2.5 rounded-[4px] font-medium whitespace-nowrap transition-colors ${view.savedOnly === only ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100"}`}
                      >
                        {only ? "Shortlist" : "All"} <span className="font-mono opacity-60">{only ? shortlistCount : final_ranked_leads.length}</span>
                      </button>
                    ))}
                  </div>
                  {campaignId && (
                    <span className="hidden lg:inline-flex">
                      <SkippedNote campaignId={campaignId} api={api} ready={status === "COMPLETED" || status === "completed"} />
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* Search: an icon that opens into a field (or press /) */}
                <label className="relative hidden md:flex items-center" title="Search (/)">
                  <Search size={14} className="absolute left-2 text-zinc-500 pointer-events-none" />
                  <input
                    ref={searchRef}
                    value={view.query}
                    onChange={(e) => set("query", e.target.value)}
                    placeholder="Search creators"
                    aria-label="Search creators"
                    className={`${view.query ? "w-52 pl-8 pr-6" : "w-[30px] pl-[28px] pr-0 focus:w-52 focus:pl-8 focus:pr-6 cursor-pointer focus:cursor-text placeholder:text-transparent focus:placeholder:text-zinc-400"} h-[30px] transition-[width] duration-200 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent hover:bg-zinc-100 dark:hover:bg-zinc-800 focus:bg-transparent focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600 text-zinc-900 dark:text-zinc-100`}
                  />
                  {view.query && (
                    <button type="button" aria-label="Clear search" onClick={() => set("query", "")} className="absolute right-2 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200">
                      <X size={12} />
                    </button>
                  )}
                </label>

                {/* Filter */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors">
                      <ListFilter size={14} />
                      Filter
                      {filterCount > 0 && (
                        <span className="min-w-4 h-4 px-1 rounded-full bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-[10px] font-semibold leading-4 text-center">
                          {filterCount}
                        </span>
                      )}
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400">
                    <DropdownMenuLabel>Signals</DropdownMenuLabel>
                    <DropdownMenuCheckboxItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" checked={view.rising} onCheckedChange={(c) => set("rising", c === true)} onSelect={(e) => e.preventDefault()}>
                      Rising only
                    </DropdownMenuCheckboxItem>
                    <DropdownMenuCheckboxItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" checked={view.onTrend} onCheckedChange={(c) => set("onTrend", c === true)} onSelect={(e) => e.preventDefault()}>
                      On trend only
                    </DropdownMenuCheckboxItem>
                    <DropdownMenuCheckboxItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" checked={view.hideSuspicious} onCheckedChange={(c) => set("hideSuspicious", c === true)} onSelect={(e) => e.preventDefault()}>
                      Hide unusual engagement
                    </DropdownMenuCheckboxItem>
                    <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
                    <DropdownMenuLabel>Confidence</DropdownMenuLabel>
                    <DropdownMenuRadioGroup value={view.confidence} onValueChange={(v) => set("confidence", v as LeadView["confidence"])}>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="All">All</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="Consider+">Hide Avoid</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="Strong Buy">Strong Buy only</DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                    <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
                    <DropdownMenuLabel>Reliability</DropdownMenuLabel>
                    <DropdownMenuRadioGroup value={view.reliability} onValueChange={(v) => set("reliability", v as LeadView["reliability"])}>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="All">All</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="High">High</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="Stable">Stable</DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                    <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
                    <DropdownMenuLabel>Price tier</DropdownMenuLabel>
                    <DropdownMenuRadioGroup value={view.price} onValueChange={(v) => set("price", v as LeadView["price"])}>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="All">All</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="Micro">Micro (&lt;$300)</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="Mid">Mid ($300-$1K)</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value="Premium">Premium (&gt;$1K)</DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                    {filterCount > 0 && (
                      <>
                        <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
                        <DropdownMenuItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" onSelect={() => setView((v) => ({ ...DEFAULT_VIEW, sort: v.sort, query: v.query, savedOnly: v.savedOnly }))}>
                          Reset filters
                        </DropdownMenuItem>
                      </>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Sort */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors">
                      <ArrowUpDown size={14} />
                      Sort
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400">
                    <DropdownMenuLabel>Sort by</DropdownMenuLabel>
                    <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
                    <DropdownMenuRadioGroup value={view.sort} onValueChange={(v) => set("sort", v as LeadView["sort"])}>
                      {SORTS.map((o) => (
                        <DropdownMenuRadioItem key={o.key} className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer" value={o.key}>
                          {o.label}
                        </DropdownMenuRadioItem>
                      ))}
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Share (view-only links) */}
                {campaignId && (
                  <ShareDialog
                    campaignId={campaignId}
                    api={api}
                    totalCount={final_ranked_leads.length}
                    selectedIds={[...selectedIds]}
                  />
                )}

                {/* Start outreach: the selected creators, else everyone in the current view */}
                {campaignId && (
                  <OutreachDialog
                    campaignId={campaignId}
                    influencers={actionTargets}
                    trigger={
                      <button
                        type="button"
                        disabled={actionTargets.length === 0}
                        className="flex items-center gap-2 h-[30px] px-3 text-xs font-medium rounded-md bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 hover:opacity-90 disabled:opacity-40 transition-opacity whitespace-nowrap"
                      >
                        <Send size={13} />
                        Start outreach
                        <span className="font-mono opacity-70">{actionTargets.length}</span>
                      </button>
                    }
                  />
                )}

                {/* ⋯ : export and keyboard shortcuts */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button aria-label="More actions" className="flex items-center justify-center h-[30px] w-[30px] rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors">
                      <MoreHorizontal size={14} />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-52 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400">
                    <DropdownMenuItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer gap-2" onSelect={() => setExportOpen(true)}>
                      <Download size={14} /> Export {actionTargets.length} as CSV
                    </DropdownMenuItem>
                    <DropdownMenuItem className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer gap-2" onSelect={() => setHelpOpen(true)}>
                      <Keyboard size={14} /> Keyboard shortcuts <span className="ml-auto font-mono text-[10px] text-zinc-400">?</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <ExportDialog influencers={actionTargets} open={exportOpen} onOpenChange={setExportOpen} trigger={null} />
              </div>
            </motion.div>

            <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
              <DialogContent className="sm:max-w-xs bg-white dark:bg-[#0c0d0e]">
                <DialogHeader>
                  <DialogTitle className="text-sm">Keyboard shortcuts</DialogTitle>
                </DialogHeader>
                <ul className="space-y-1.5">
                  {SHORTCUTS.map(([k, what]) => (
                    <li key={k} className="flex items-center justify-between text-xs">
                      <span>{what}</span>
                      <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded border border-zinc-200 dark:border-zinc-700 text-zinc-500">{k}</kbd>
                    </li>
                  ))}
                </ul>
              </DialogContent>
            </Dialog>

            {/* --- RUN NOTE + PLATFORM CHIPS --- */}
            {platforms.length > 1 && (
              <div className="flex items-center gap-2 -mt-3 mb-1">
                <div className="w-10 flex-shrink-0" />
                <div className="flex-1 min-w-0 flex flex-wrap items-center justify-between gap-2 pl-1">
                  {platforms.length > 1 && (
                    <div className="flex items-center gap-1" role="group" aria-label="Platforms">
                      {[{ platform: "all", count: final_ranked_leads.length }, ...platforms].map(({ platform, count }) => {
                        const on = platform === "all" ? view.platforms.length === 0 : view.platforms.includes(platform);
                        return (
                          <button
                            key={platform}
                            type="button"
                            aria-pressed={on}
                            onClick={() =>
                              set("platforms", platform === "all" ? [] : on ? view.platforms.filter((p) => p !== platform) : [...view.platforms, platform])
                            }
                            className={`px-2 py-0.5 rounded-md border text-[11px] font-medium transition-colors ${on ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900" : "border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
                          >
                            {PLATFORM_NAMES[platform] ?? platform} <span className="font-mono opacity-60">{count}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* --- CAMPAIGN SUMMARY BANNER --- */}
            <motion.div variants={staggerItemVariants}  className="flex items-stretch gap-2 mb-4">
              <div className="w-10 flex-shrink-0" />
              <div className="flex-1 min-w-0  ">
                <CampaignSummaryBanner
                  influencers={
                    selectedIds.size > 0
                      ? displayedLeads.filter((l) => selectedIds.has(l.id))
                      : displayedLeads
                  }
                />
              </div>
            </motion.div>

            {/* --- INFLUENCER LIST --- */}
            <div className="flex flex-col gap-2">
              {displayedLeads.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 text-center bg-zinc-100/50 dark:bg-zinc-900/50 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-800">
                  <p className="text-zinc-500">
                    {view.savedOnly && shortlistCount === 0
                      ? "Your shortlist is empty. Click the bookmark on a creator to add them."
                      : view.query
                        ? `No creators match “${view.query}” with these filters.`
                        : "No creators match these filters."}
                  </p>
                  {view.savedOnly && shortlistCount === 0 ? (
                    <button
                      type="button"
                      onClick={() => set("savedOnly", false)}
                      className="mt-3 px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                    >
                      Show all creators
                    </button>
                  ) : (
                  <button
                    type="button"
                    onClick={() => setView((v) => ({ ...DEFAULT_VIEW, sort: v.sort, savedOnly: v.savedOnly }))}
                    className="mt-3 px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                  >
                    Clear search and filters
                  </button>
                  )}
                </div>
              ) : (
                displayedLeads.map((influencer, index) => {
                  const isSelected = selectedIds.has(influencer.id);
                  const isCursor = cursor === index;
                  return (
                    <motion.div variants={staggerItemVariants}
                      key={influencer.id}
                      data-lead-index={index}
                      className="group flex items-stretch gap-2"
                    >
                      {/* Independent Checkbox Column (Hidden by default) */}
                      <div
                        onClick={() => toggleSelection(influencer.id)}
                        className={`w-10 rounded-lg border flex items-center justify-center cursor-pointer transition-all duration-200 ${isSelected ? "opacity-100 scale-100 border-zinc-300 dark:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/20" : "opacity-0 scale-95 group-hover:opacity-100 group-hover:scale-100 border-zinc-200/50 dark:border-zinc-800/50 bg-white dark:bg-[#0c0d0e] hover:border-zinc-300/50 dark:hover:border-zinc-700/50"}`}
                      >
                        <div
                          className={`w-[13px] h-[13px] rounded-[3px] border flex items-center justify-center transition-colors ${isSelected ? "border-zinc-900 bg-zinc-900 dark:border-[#ededed] dark:bg-[#ededed]" : "border-zinc-300 dark:border-white/10 bg-white dark:bg-transparent hover:border-zinc-400 dark:hover:border-white/30"}`}
                        >
                          {isSelected && (
                            <svg
                              width="8"
                              height="6"
                              viewBox="0 0 9 7"
                              fill="none"
                              xmlns="http://www.w3.org/2000/svg"
                              className="text-white dark:text-[#0a0a0a]"
                            >
                              <path
                                d="M1 3.5L3.5 6L8 1"
                                stroke="currentColor"
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          )}
                        </div>
                      </div>

                      {/* Sheet Trigger Column */}
                      <div className="flex-1 min-w-0">
                        <Sheet
                          open={openId === influencer.id}
                          onOpenChange={(o) => {
                            setOpenId(o ? influencer.id : null);
                            if (!o && !keyboardNav.current) setCursor(null);
                          }}
                        >
                            <div
                              role="button"
                              tabIndex={-1}
                              onClick={() => {
                                keyboardNav.current = false;
                                setCursor(index);
                                setOpenId(influencer.id);
                              }}
                              className={`h-full rounded-lg border overflow-hidden cursor-pointer transition-colors ${isCursor ? "border-zinc-400 dark:border-zinc-500" : isSelected ? "border-zinc-300 dark:border-zinc-600" : "border-zinc-200/50 dark:border-zinc-800/50 hover:border-zinc-300/50 dark:hover:border-zinc-700/50"}`}
                            >
                              <InfluencerRow
                                influencer={influencer}
                                rank={index + 1}
                                isSelected={isSelected}
                                isSaved={!!savedLeadsMap[influencer.id]}
                                feedback={feedback[influencer.id]}
                                onToggleSave={(lead) => campaignId && toggleSaveLead(campaignId, lead, api)}
                              />
                            </div>
                          <InfluencerDetailSheet influencer={influencer} campaignId={campaignId} feedback={feedback[influencer.id]} />
                        </Sheet>
                      </div>
                    </motion.div>
                  );
                })
              )}
            </div>
          </div>

          <CompareTray
            open={compareOpen}
            onOpenChange={setCompareOpen}
            leads={(final_ranked_leads ?? []).filter((l) => selectedIds.has(l.id))}
          />

          {/* A save that didn't reach the server (the bookmark has already been put back) */}
          <AnimatePresence>
            {saveError && (
              <motion.div
                role="status"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ duration: 0.16 }}
                className={`fixed ${selectedIds.size ? "bottom-20" : "bottom-6"} right-6 z-50 px-3 py-2 rounded-lg text-xs font-medium bg-rose-600 text-white shadow-xl`}
              >
                {saveError}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Floating Action Bar for Selected Leads */}
          <AnimatePresence>
            {selectedIds.size > 0 && campaignId && (
              <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 30 }}
                transition={{ duration: 0.18, ease: "easeOut" }}
                className="fixed bottom-6 inset-x-0 z-40 flex justify-center pointer-events-none px-4"
              >
                <div className="pointer-events-auto flex items-center gap-3 px-4 py-2.5 rounded-full bg-zinc-900/95 dark:bg-[#121314]/95 backdrop-blur-md border border-zinc-700/60 dark:border-white/10 shadow-2xl text-white text-xs">
                  <span className="font-medium text-zinc-200">
                    {selectedIds.size} {selectedIds.size === 1 ? "creator" : "creators"} selected
                  </span>

                  <div className="w-[1px] h-3.5 bg-zinc-700 dark:bg-zinc-800" />

                  <OutreachDialog
                    campaignId={campaignId}
                    influencers={displayedLeads.filter((l) => selectedIds.has(l.id))}
                    trigger={
                      <button
                        type="button"
                        className="flex items-center gap-1.5 px-3 py-1 font-medium bg-white text-zinc-900 dark:bg-white dark:text-zinc-900 rounded-full hover:bg-zinc-100 transition-colors shadow-sm"
                      >
                        <Send size={12} />
                        Start Outreach
                      </button>
                    }
                  />

                  <ExportDialog
                    influencers={displayedLeads.filter((l) => selectedIds.has(l.id))}
                  />

                  <button
                    type="button"
                    disabled={selectedIds.size < 2 || selectedIds.size > MAX_COMPARE}
                    title={selectedIds.size < 2 ? "Select 2 to 4 creators to compare" : selectedIds.size > MAX_COMPARE ? `Compare up to ${MAX_COMPARE} at a time` : "Compare side by side"}
                    onClick={() => setCompareOpen(true)}
                    className="px-2.5 py-1 font-medium rounded-full border border-zinc-600 text-zinc-100 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Compare
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedIds(new Set())}
                    className="text-zinc-400 hover:text-white px-1.5 py-0.5 transition-colors"
                  >
                    Clear
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </TooltipProvider>
    // </StaggerFadeRise>
  );
};

export default InfluencerPage;
