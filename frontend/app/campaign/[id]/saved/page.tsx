import SavedLeadsClient from "./SavedLeadsClient";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!id) return <div>Campaign not found</div>;

  return <SavedLeadsClient campaignId={id} />;
}