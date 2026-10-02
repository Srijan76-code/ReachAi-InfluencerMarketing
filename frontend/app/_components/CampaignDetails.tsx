import RadioCards from "@/components/CampaignGoal";
import React from "react";
import CreatorAuthority from "@/components/CreatorAuthority";
import FlagAndSearchCountry from "@/components/FlagAndSearchCountry";
import MultiPlatform from "@/components/MultiPlatform";
import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";

const CampaignDetails = () => {
  return (
    <div className="group relative border border-zinc-200 dark:border-zinc-800 p-6 rounded-xl bg-white dark:bg-[#0c0d0e]">
      <div className="-translate-y-1/2 text-[13px] font-medium absolute start-3 top-0 z-10 block px-2 bg-white dark:bg-[#0c0d0e]">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground text-[13px]">
            Campaign Details
          </StatusLabel>
        </Status>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-2">
        <RadioCards />
        <CreatorAuthority />
        <MultiPlatform />
        <FlagAndSearchCountry />
      </div>
    </div>
  );
};

export default CampaignDetails;
