import RadioCards from "@/components/CampaignGoal";
import React from "react";
import CreatorAuthority from "@/components/CreatorAuthority";
import FlagAndSearchCountry from "@/components/FlagAndSearchCountry";
import MultiPlatform from "@/components/MultiPlatform";
import Competitors from "@/components/Competitors";
import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";

const CampaignDetails = () => {
  return (
    <div className="group relative border border-zinc-200 dark:border-zinc-800 p-7 rounded-xl bg-white dark:bg-[#0c0d0e]">
      <div className="-translate-y-1/2 text-[13px] font-medium absolute start-3 top-0 z-10 block px-2 bg-white dark:bg-[#0c0d0e]">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground text-[13px]">
            Campaign Details
          </StatusLabel>
        </Status>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-7 gap-y-8 mt-3">
        <RadioCards />
        <CreatorAuthority />
        <MultiPlatform />
        <FlagAndSearchCountry />
        <Competitors />
      </div>
    </div>
  );
};

export default CampaignDetails;
