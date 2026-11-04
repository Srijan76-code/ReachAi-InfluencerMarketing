import type { Metadata } from "next";
import SharedShortlist from "./SharedShortlist";

// Shared shortlists are private to whoever holds the link: never indexed, never sent as a referrer.
export const metadata: Metadata = {
  title: "Shared shortlist · ReachAI",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function SharedPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <SharedShortlist token={token} />;
}
