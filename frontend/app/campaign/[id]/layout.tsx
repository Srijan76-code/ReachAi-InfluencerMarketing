import CampaignTabs from "./CampaignTabs";

export default async function layout({
  children,
  params,
}: Readonly<{ children: React.ReactNode; params: Promise<{ id: string }> }>) {
  const { id } = await params;
  if (!id) return <div>Id not found</div>;

  return (
    <div>
      <CampaignTabs id={id} />
      {children}
    </div>
  );
}
