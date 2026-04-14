import CampaignTabs from "./CampaignTabs";

export default async function layout({
  children,
  params,
}: Readonly<{ children: React.ReactNode; params: Promise<{ id: string }> }>) {
  const { id } = await params;
  if (!id) return <div>Id not found</div>;

 return (

      <main className="pt-14"> 
         <CampaignTabs id={id} />
         <div className="max-w-7xl mx-auto p-6 md:p-16 bg-zinc-50 dark:bg-[#08090a]">
            {children}
         </div>
      </main>
    
  );
}
