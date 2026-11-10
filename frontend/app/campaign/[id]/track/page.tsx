import { Suspense } from "react";
import TrackBoard from "@/components/track/TrackBoard";

/** Track: was it worth it? Posts, views, clicks, signups, who to rebook, and who to pay (spec §7.6). */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={null}>
      <TrackBoard campaignId={id} />
    </Suspense>
  );
}
