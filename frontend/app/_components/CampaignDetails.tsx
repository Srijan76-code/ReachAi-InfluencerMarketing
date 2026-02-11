import ListboxOptions from "@/components/ListboxOptions";
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
    <div className="group relative border p-8 rounded-xl mt-16 grid grid-cols-1  lg:grid-cols-2 gap-16 w-full">
      <div className="-translate-y-1/2 text-sm font-medium absolute start-1 top-0 z-10 block px-2   ">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground  ">
            Campaign Details
          </StatusLabel>
        </Status>
      </div>

      <RadioCards />
      <CreatorAuthority />
      
      <MultiPlatform />
      <FlagAndSearchCountry />

    </div>
  );
};

export default CampaignDetails;
