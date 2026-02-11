
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
import TotalBudget from "@/components/TotalBudget";
import RangeSlider from "@/components/RangeSlider";
import MultiTabs from "@/components/MultiTabs";

const Constraints = () => {
  return (
    <div className="group relative border p-8 rounded-xl mt-16 space-y-16">
      <div className="-translate-y-1/2 text-sm font-medium absolute start-1 top-0 z-10 block px-2   ">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground  ">
            Constraints
          </StatusLabel>
        </Status>
      </div>

      <MultiTabs/>


    

    </div>
  );
};

export default Constraints;
