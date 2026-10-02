"use client";

import { SmartAudienceInput } from "./SmartAudienceInput";
import { SmartAudienceInput2 } from "./SmartAudienceInput2";
import RangeSlider from "@/components/RangeSlider";
import { useCampaignStore } from "@/store/campaignStore";
import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";

const AudienceDetails = () => {
  const creatorSize = useCampaignStore((state) => state.creatorSize);
  const setField = useCampaignStore((state) => state.setField);

  return (
    <div className="group relative border border-zinc-200 dark:border-zinc-800 p-6 rounded-xl space-y-5 bg-white dark:bg-[#0c0d0e]">
      <div className="-translate-y-1/2 text-[13px] font-medium absolute start-3 top-0 z-10 block px-2 bg-white dark:bg-[#0c0d0e]">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground text-[13px]">
            Audience Details
          </StatusLabel>
        </Status>
      </div>
      <SmartAudienceInput />
      <SmartAudienceInput2 />
      <RangeSlider
        value={creatorSize}
        onChange={(val) => setField("creatorSize", val)}
        label="Creator size (subscriber count)"
      />
    </div>
  );
};

export default AudienceDetails;
