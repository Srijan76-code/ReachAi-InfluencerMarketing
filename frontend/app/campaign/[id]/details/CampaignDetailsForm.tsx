"use client";

import React, { useEffect } from "react";
import { Loader2 } from "lucide-react";
import BrandDetails from "@/app/_components/BrandDetails";
import CampaignDetails from "@/app/_components/CampaignDetails";
import AudienceDetails from "@/app/_components/AudienceDetails";
import Constraints from "@/app/_components/Constraints";
import SubmitCampaignButton from "@/app/campaign/[id]/details/SubmitCampaignButton";
import { useCampaignStore } from "@/store/campaignStore";
import { useApi } from "@/lib/api";

export default function CampaignDetailsForm({ id }: { id: string }) {
  const loadCampaignFromCacheOrFetch = useCampaignStore((state) => state.loadCampaignFromCacheOrFetch);
  const isLoadingCampaign = useCampaignStore((state) => state.isLoadingCampaign);
  const brandName = useCampaignStore((state) => state.brandName);
  const api = useApi();

  useEffect(() => {
    if (id) {
      loadCampaignFromCacheOrFetch(id, api);
    }
  }, [id]);

  if (isLoadingCampaign && !brandName) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] flex items-center justify-center p-8">
        <div className="flex items-center gap-3 text-zinc-500 text-xs">
          <Loader2 size={16} className="animate-spin text-zinc-400" />
          <span>Loading campaign details...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] text-zinc-600 dark:text-zinc-400 p-8 font-sans">
      <div className="max-w-3xl mx-auto space-y-5">
        {/* Page header */}
        <div className="flex items-center justify-between px-1 py-2">
          <div className="space-y-1">
            <h1 className="text-[16px] font-medium text-zinc-900 dark:text-zinc-100 tracking-tight">
              Campaign details
            </h1>
            <p className="text-[12px] text-zinc-500">
              Configure your brand, campaign goals, and audience targeting.
            </p>
          </div>
        </div>

        <BrandDetails />
        <CampaignDetails />
        <AudienceDetails />
        <Constraints />
        <SubmitCampaignButton id={id} />
      </div>
    </div>
  );
}
