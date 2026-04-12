"use client";

import React from "react";
import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";
import TotalBudget from "@/components/TotalBudget";
import NumberOfCreator from "@/components/NumberOfCreator";
import { useCampaignStore } from "@/store/campaignStore";

const Constraints = () => {
  const numberOfCreators = useCampaignStore((state) => state.numberOfCreators);
  const setField = useCampaignStore((state) => state.setField);

  return (
    <div className="group relative border p-8 rounded-xl mt-16 space-y-16">
      <div className="-translate-y-1/2 text-[13px] font-medium absolute start-1 top-0 z-10 block px-2">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground text-[13px]">
            Constraints
          </StatusLabel>
        </Status>
      </div>

      <div className="space-y-8 mt-8">
        <TotalBudget />
        <NumberOfCreator value={numberOfCreators} onChange={(val) => setField("numberOfCreators", val)} />
      </div>

    </div>
  );
};

export default Constraints;
