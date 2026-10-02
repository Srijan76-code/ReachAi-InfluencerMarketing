import InfluencerPage from "@/app/ListOfInfluencer/InfluencerPage";
import { CampaignProgressBanner } from "@/components/CampaignProgressBanner";

const page = async ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  return (
    <div className="max-w-full overflow-x-hidden">
      <CampaignProgressBanner campaignId={id} />
      <InfluencerPage campaignId={id} />
    </div>
  );
};

export default page;
