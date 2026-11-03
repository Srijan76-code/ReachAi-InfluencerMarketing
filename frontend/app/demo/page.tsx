import type { Metadata } from "next";
import DemoCampaign from "./DemoCampaign";

export const metadata: Metadata = {
  title: "Demo campaign · ReachAI",
  description: "See a ReachAI campaign end to end: the brief, ranked creators, fair prices and outreach pitches.",
};

export default function DemoPage() {
  return <DemoCampaign />;
}
