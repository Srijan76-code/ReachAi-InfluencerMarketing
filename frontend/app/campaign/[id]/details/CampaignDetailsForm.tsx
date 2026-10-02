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
        <div className="flex items-center gap-2.5 text-zinc-500 text-xs">
          <Loader2 size={16} className="animate-spin text-zinc-400" />
          <span>Loading campaign details...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-full overflow-x-hidden my-36 font-raleway text-[13px] bg-zinc-50 dark:bg-[#08090a]">
      <div className="max-w-4xl px-16 lg:px-0 flex flex-col flex-wrap mx-auto space-y-16 bg-zinc-50 dark:bg-[#08090a]">
        <BrandDetails />
        <CampaignDetails />
        <AudienceDetails />
        <Constraints />
        <SubmitCampaignButton id={id} />
      </div>
    </div>
  );
}
