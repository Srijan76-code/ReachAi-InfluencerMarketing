"use client";

import React from "react";
import TotalBudget from "@/components/TotalBudget";
import NumberOfCreator from "@/components/NumberOfCreator";
import { useCampaignStore } from "@/store/campaignStore";
import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";

const Constraints = () => {
  const numberOfCreators = useCampaignStore((state) => state.numberOfCreators);
  const setField = useCampaignStore((state) => state.setField);

  return (
    <div className="group relative border border-zinc-200 dark:border-zinc-800 p-6 rounded-xl space-y-5 bg-white dark:bg-[#0c0d0e]">
      <div className="-translate-y-1/2 text-[13px] font-medium absolute start-3 top-0 z-10 block px-2 bg-white dark:bg-[#0c0d0e]">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground text-[13px]">
            Budget &amp; reach
          </StatusLabel>
        </Status>
      </div>
      <TotalBudget />
      <NumberOfCreator value={numberOfCreators} onChange={(val) => setField("numberOfCreators", val)} />
    </div>
  );
};

export default Constraints;
