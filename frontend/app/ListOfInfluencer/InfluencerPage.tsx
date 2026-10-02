"use client";

import React, { useState, useMemo, useEffect } from "react";
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
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetTrigger } from "@/components/ui/sheet";
import { InfluencerDetailSheet } from "./InfluencerDetailSheet";
import { ExportDialog } from "@/components/ExportDialog";
import { OutreachDialog } from "@/components/OutreachDialog";
import { CampaignSummaryBanner } from "./CampaignSummaryBanner";
import { motion, AnimatePresence } from "motion/react";
import { staggerItemVariants } from "@/components/animations/variants";

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

  // Sorting and Filtering states
  const [sortBy, setSortBy] = useState("optimal");
  const [filterConfidence, setFilterConfidence] = useState("All");
  const [filterReliability, setFilterReliability] = useState("All");
  const [filterPrice, setFilterPrice] = useState("All");

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const displayedLeads = useMemo(() => {
    if (!final_ranked_leads || !Array.isArray(final_ranked_leads)) return [];

    // 1. FILTERING
    const filtered = final_ranked_leads.filter((lead) => {
      // Confidence
      if (filterConfidence !== "All") {
        if (lead.deal_status !== filterConfidence) return false;
      }
      // Reliability (Stable = High or Medium)
      if (filterReliability !== "All") {
        const rel = lead.metrics?.reliability;
        if (filterReliability === "High" && rel !== "High") return false;
        if (
          filterReliability === "Stable" &&
          rel !== "High" &&
          rel !== "Medium"
        )
          return false;
      }
      // Price Tier
      if (filterPrice !== "All") {
        const price = lead.valuation || 0;
        if (filterPrice === "Micro" && price >= 300) return false;
        if (filterPrice === "Mid" && (price < 300 || price > 1000))
          return false;
        if (filterPrice === "Premium" && price <= 1000) return false;
      }
      return true;
    });

    // 2. SORTING
    filtered.sort((a, b) => {
      if (sortBy === "optimal") {
        return (b.final_score || 0) - (a.final_score || 0);
      }
      if (sortBy === "yield") {
        const aYield = parseInt(String(a.metrics?.forecast || "").replace(/[^0-9]/g, "")) || 0;
        const bYield = parseInt(String(b.metrics?.forecast || "").replace(/[^0-9]/g, "")) || 0;
        return bYield - aYield;
      }
      if (sortBy === "authority") {
        return (b.metrics?.trust_score || 0) - (a.metrics?.trust_score || 0);
      }
      if (sortBy === "budget") {
        return (a.valuation || 0) - (b.valuation || 0);
      }
      return 0;
    });

    return filtered;
  }, [
    final_ranked_leads,
    sortBy,
    filterConfidence,
    filterReliability,
    filterPrice,
  ]);

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

  const toggleSelection = (id: string) => {
    setSelectedIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) newSet.delete(id);
      else newSet.add(id);
      return newSet;
    });
  };

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

                {/* Title & Contextual Counter */}
                <div className="flex items-center gap-2 border-l border-transparent pl-1">
                  {selectedIds.size > 0 ? (
                    <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">
                      {selectedIds.size} selected
                    </span>
                  ) : (
                    <>
                      <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100 tracking-tight">
                        Influencer Leads
                      </h1>
                      {/* <div className="px-1.5 py-0.5 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 flex items-center justify-center">
                        <span className="text-[11px] font-mono font-medium text-zinc-500 dark:text-zinc-400 leading-none">
                          {String(displayedLeads.length).padStart(2, "0")}
                        </span>
                      </div> */}
                    </>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* Sort & Filter */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors">
                      <ArrowUpDown size={14} />
                      Sort
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    className="w-48 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400"
                  >
                    <DropdownMenuLabel>Priority</DropdownMenuLabel>
                    <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
                    <DropdownMenuRadioGroup
                      value={sortBy}
                      onValueChange={setSortBy}
                    >
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="optimal"
                      >
                        Optimal (AI Rank)
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="yield"
                      >
                        High Intent (Yield)
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="authority"
                      >
                        Authority (Trust)
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="budget"
                      >
                        Fair Value (Budget First)
                      </DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors">
                      <ListFilter size={14} />
                      Filter
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    className="w-48 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400"
                  >
                    <DropdownMenuLabel>Confidence</DropdownMenuLabel>
                    <DropdownMenuRadioGroup
                      value={filterConfidence}
                      onValueChange={setFilterConfidence}
                    >
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="All"
                      >
                        All
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="Strong Buy"
                      >
                        Strong Buy Only
                      </DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>

                    <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />

                    <DropdownMenuLabel>Reliability</DropdownMenuLabel>
                    <DropdownMenuRadioGroup
                      value={filterReliability}
                      onValueChange={setFilterReliability}
                    >
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="All"
                      >
                        All
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="High"
                      >
                        High
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="Stable"
                      >
                        Stable
                      </DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>

                    <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />

                    <DropdownMenuLabel>Price Tier</DropdownMenuLabel>
                    <DropdownMenuRadioGroup
                      value={filterPrice}
                      onValueChange={setFilterPrice}
                    >
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="All"
                      >
                        All
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="Micro"
                      >
                        Micro (&lt;$300)
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="Mid"
                      >
                        Mid ($300-$1K)
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        className="focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer"
                        value="Premium"
                      >
                        Premium (&gt;$1K)
                      </DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Outreach Action Trigger */}
                {campaignId && (
                  <OutreachDialog
                    campaignId={campaignId}
                    influencers={
                      selectedIds.size > 0
                        ? displayedLeads.filter((l) => selectedIds.has(l.id))
                        : displayedLeads
                    }
                  />
                )}

                {/* Export Advanced Module */}
                <ExportDialog
                  influencers={
                    selectedIds.size > 0
                      ? displayedLeads.filter((l) => selectedIds.has(l.id))
                      : displayedLeads
                  }
                />
              </div>
            </motion.div>

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
                    No influencers match these strict guardrails.
                  </p>
                </div>
              ) : (
                displayedLeads.map((influencer, index) => {
                  const isSelected = selectedIds.has(influencer.id);
                  return (
                    <motion.div variants={staggerItemVariants}
                      key={influencer.id}
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
                        <Sheet>
                          <SheetTrigger asChild>
                            <div
                              className={`h-full rounded-lg border overflow-hidden cursor-pointer transition-colors ${isSelected ? "border-zinc-300 dark:border-zinc-600" : "border-zinc-200/50 dark:border-zinc-800/50 hover:border-zinc-300/50 dark:hover:border-zinc-700/50"}`}
                            >
                              <InfluencerRow
                                influencer={influencer}
                                rank={index + 1}
                                isSelected={isSelected}
                                isSaved={!!savedLeadsMap[influencer.id]}
                                onToggleSave={(lead) => campaignId && toggleSaveLead(campaignId, lead, api)}
                              />
                            </div>
                          </SheetTrigger>
                          <InfluencerDetailSheet influencer={influencer} campaignId={campaignId} />
                        </Sheet>
                      </div>
                    </motion.div>
                  );
                })
              )}
            </div>
          </div>

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
