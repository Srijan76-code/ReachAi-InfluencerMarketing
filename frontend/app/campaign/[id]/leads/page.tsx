import InfluencerPage from "@/app/ListOfInfluencer/InfluencerPage";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <div className="max-w-full overflow-x-hidden">
      <InfluencerPage campaignId={id} />
    </div>
  );
}
