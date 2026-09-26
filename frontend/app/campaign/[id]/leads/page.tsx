
import InfluencerPage from "@/app/ListOfInfluencer/InfluencerPage";
import WorkflowStatus from "../WorkflowStatus";

const page = async ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  return (
    <div className="max-w-full  overflow-x-hidden ">
        <WorkflowStatus campaignId={id} />
        <InfluencerPage />

    </div>
  );
};

export default page;
