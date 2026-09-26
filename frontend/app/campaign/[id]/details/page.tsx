import CampaignDetailsForm from "@/app/campaign/[id]/details/CampaignDetailsForm";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!id) return <div>Id not found</div>;

  return <CampaignDetailsForm id={id} />;
}

