"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { useCampaignStore } from "@/store/campaignStore";
import { useApi } from "@/lib/api";
import { InfluencerRow } from "@/app/ListOfInfluencer/InfluencerRow";
import { Sheet, SheetTrigger } from "@/components/ui/sheet";
import { InfluencerDetailSheet } from "@/app/ListOfInfluencer/InfluencerDetailSheet";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Bookmark, Users } from "lucide-react";

export default function SavedLeadsClient({ campaignId }: { campaignId: string }) {
  const api = useApi();
  const savedLeadsList = useCampaignStore((state) => state.savedLeadsList);
  const savedLeadsMap = useCampaignStore((state) => state.savedLeadsMap);
  const fetchSavedLeads = useCampaignStore((state) => state.fetchSavedLeads);
  const toggleSaveLead = useCampaignStore((state) => state.toggleSaveLead);

  useEffect(() => {
    if (campaignId) {
      fetchSavedLeads(campaignId, api);
    }
  }, [campaignId]);

  const influencers = savedLeadsList.map((item) => item.lead_data).filter(Boolean);

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] pt-24 pb-20 px-6 sm:px-12 font-sans">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between pb-6 mb-8 border-b border-zinc-200/60 dark:border-zinc-800/60">
            <div>
              <div className="flex items-center gap-2">
                <Bookmark className="w-4 h-4 text-amber-500 fill-amber-500" />
                <h1 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                  Saved Leads
                </h1>
              </div>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                Bookmarked creators for this campaign.
              </p>
            </div>
            <div className="text-xs font-mono text-zinc-500">
              {influencers.length} {influencers.length === 1 ? "Creator" : "Creators"} Saved
            </div>
          </div>

          {/* List */}
          {influencers.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl bg-white/50 dark:bg-[#0c0d0e]/50 text-center p-8">
              <div className="h-10 w-10 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mb-3">
                <Bookmark className="text-zinc-400" size={18} />
              </div>
              <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                No saved leads yet
              </h3>
              <p className="text-xs text-zinc-500 mt-1 mb-4">
                Bookmark creators from the Leads tab to access them quickly here.
              </p>
              <Link
                href={`/campaign/${campaignId}/leads`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 hover:opacity-90 transition-opacity"
              >
                <Users size={13} />
                <span>Go to Leads</span>
              </Link>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {influencers.map((influencer, index) => {
                const leadId = influencer.id;
                return (
                  <div key={leadId} className="flex-1 min-w-0">
                    <Sheet>
                      <SheetTrigger asChild>
                        <div className="h-full rounded-lg border overflow-hidden cursor-pointer border-zinc-200/50 dark:border-zinc-800/50 hover:border-zinc-300/50 dark:hover:border-zinc-700/50 transition-colors">
                          <InfluencerRow
                            influencer={influencer}
                            rank={index + 1}
                            isSaved={!!savedLeadsMap[leadId]}
                            onToggleSave={(lead) => toggleSaveLead(campaignId, lead, api)}
                          />
                        </div>
                      </SheetTrigger>
                      <InfluencerDetailSheet influencer={influencer} />
                    </Sheet>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
