import React from "react";
import BrandDetails from "@/app/_components/BrandDetails";
import CampaignDetails from "@/app/_components/CampaignDetails";
import { Skiper26 } from "@/components/ui/skiper-ui/skiper26";

import AudienceDetails from "@/app/_components/AudienceDetails";
import Constraints from "@/app/_components/Constraints";
import SubmitCampaignButton from "@/components/SubmitCampaignButton";

const page = () => {
  return (
    <div>
   
   
    <div className="max-w-full overflow-x-hidden my-36 font-raleway text-[13px]">
      <div className=" ">
        {/* <Skiper26 /> */}
      </div>
      <div className="max-w-4xl px-16 lg:px-0 flex flex-col flex-wrap mx-auto space-y-16 ">
        <BrandDetails />
        <CampaignDetails />
        <AudienceDetails />
        <Constraints />
        <SubmitCampaignButton />
      </div>
    </div>
     </div>
  );
};

export default page;
