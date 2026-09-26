"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";

import { useCampaignStore, CampaignState } from "@/store/campaignStore";
import { Button } from "@/components/ui/button";

function transformPayload(store: CampaignState) {
  const tickToNumber: Record<number, number> = {
    1: 1000, 2: 5000, 3: 10000, 4: 20000, 5: 50000, 6: 100000,
    7: 200000, 8: 500000, 9: 1000000, 10: 2000000, 11: 5000000,
    12: 10000000, 13: 12000000,
  };
  const businessModelMap: Record<string, string> = { "1": "b2b", "2": "b2c", "3": "d2c" };
  const priceRangeMap: Record<string, string> = { "1": "low_ticket", "2": "mid_ticket", "3": "high_ticket" };
  const goalMap: Record<string, string> = { "1": "awareness", "2": "signups", "3": "sales" };
  const authorityMap: Record<string, string> = { "1": "peer", "2": "mentor", "3": "expert" };
  const platformMap: Record<string, string> = { "1": "youtube", "2": "instagram" };
  const getCountryCode = (name: string) => name ? name.substring(0, 2).toUpperCase() : "IN";

  return {
    brand: {
      name: store.brandName || "DataLaunch",
      website: "https://datalaunch.io",
      industry: store.industry || "edtech",
      business_model: businessModelMap[store.businessModel] || "b2c",
      product_price_range: priceRangeMap[store.productPriceRange] || "high_ticket",
      core_outcome: store.pitch || "A 12-week intensive Data Science bootcamp.",
    },
    audience: {
      target_persona: store.targetAudience || "Junior developers and fresh CS graduates.",
      locations: [getCountryCode(store.audienceLocation)],
      languages: ["en", "hi"],
    },
    campaign: {
      goal: goalMap[store.campaignGoal] || "signups",
      creator_authority_level: authorityMap[store.creatorAuthority] || "mentor",
      platform: platformMap[store.platforms[0]] || "youtube",
      budget_total: parseInt(store.totalBudget) || 5000,
      creator_count: store.numberOfCreators[0] || 5,
    },
    constraints: {
      min_subscribers: tickToNumber[store.creatorSize[0]] || 10000,
      max_subscribers: tickToNumber[store.creatorSize[1]] || 500000,
      target_countries: [getCountryCode(store.audienceLocation)],
      exclude_kids_content: true,
    },
  };
}

export default function SubmitCampaignButton({ id }: { id: string }) {
  const store = useCampaignStore();
  const router = useRouter();
  const { getToken } = useAuth();

  const handleSubmit = async () => {
    const finalPayload = transformPayload(store);
    store.setField("isGenerating", true);
    store.setField("finalInfluencers", null);
    store.setField("currentStage", "Starting LangGraph agent...");
    store.setField("stageIndex", "0/9");
    router.push(`/campaign/${id}/leads`);

    try {
      const token = await getToken();
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}/api/campaigns/${id}/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(finalPayload),
        },
      );
      if (!response.ok) throw new Error("Unable to enqueue campaign workflow");
    } catch (error) {
      console.error("Error submitting campaign to backend:", error);
      store.setField("isGenerating", false);
    }
  };

  return (
    <Button variant="secondary" size="lg" onClick={handleSubmit} className="w-full mt-8">
      Submit Campaign
    </Button>
  );
}
