import { Suspense } from "react";
import DealsBoard from "@/components/deals/DealsBoard";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={null}>
      <DealsBoard campaignId={id} />
    </Suspense>
  );
}
