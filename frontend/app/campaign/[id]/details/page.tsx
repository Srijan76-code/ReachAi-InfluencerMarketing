import React from "react";
import BrandDetails from "@/app/_components/BrandDetails";
import CampaignDetails from "@/app/_components/CampaignDetails";


import AudienceDetails from "@/app/_components/AudienceDetails";
import Constraints from "@/app/_components/Constraints";
import SubmitCampaignButton from "@/app/campaign/[id]/details/SubmitCampaignButton";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  if (!id) return <div>Id not found</div>;

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
        <SubmitCampaignButton id={id} />
      </div>
    </div>
     </div>
  );
};

