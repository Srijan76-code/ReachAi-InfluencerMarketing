"use client";

import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";
import { SmartAudienceInput } from "./SmartAudienceInput";
import { SmartAudienceInput2 } from "./SmartAudienceInput2";
import RangeSlider from "@/components/RangeSlider";

import { useCampaignStore } from "@/store/campaignStore";

const AudienceDetails = () => {
  const creatorSize = useCampaignStore((state) => state.creatorSize);
  const setField = useCampaignStore((state) => state.setField);
  
  return (
    <div className="group relative border p-8 rounded-xl mt-16 space-y-16 ">
      <div className="-translate-y-1/2 text-sm font-medium absolute start-1 top-0 z-10 block px-2   ">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground  ">
            Audience Details
          </StatusLabel>
        </Status>
      </div>

      <SmartAudienceInput />
      <SmartAudienceInput2 />
      <RangeSlider value={creatorSize} onChange={(val) => setField("creatorSize", val)} label="Creator Size (Subscriber count)" />
    </div>
  );
};

export default AudienceDetails;
