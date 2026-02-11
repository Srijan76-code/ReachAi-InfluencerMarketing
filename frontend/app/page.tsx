import React from "react";
import BrandDetails from "./_components/BrandDetails";
import CampaignDetails from "./_components/CampaignDetails";
import { Skiper26 } from "@/components/ui/skiper-ui/skiper26";

import AudienceDetails from "./_components/AudienceDetails";
import Constraints from "./_components/Constraints";

const page = () => {
  return (
    <div className="max-w-full overflow-x-hidden my-36">
            <div className=" ">
        <Skiper26  />
      </div>
      <div className="max-w-4xl px-16 lg:px-0 flex flex-col flex-wrap mx-auto space-y-16 ">

      <BrandDetails />
      <CampaignDetails />
      <AudienceDetails />
      <Constraints/>

      
      </div>

    </div>
  );
};

export default page;
