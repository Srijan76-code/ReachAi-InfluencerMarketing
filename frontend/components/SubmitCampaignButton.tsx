"use client";

import { useCampaignStore, CampaignState } from "@/store/campaignStore";
import { Button } from "@/components/ui/button";

function transformPayload(store: CampaignState) {
  const tickToNumber: Record<number, number> = {
    1: 1000, 2: 5000, 3: 10000, 4: 20000, 5: 50000,
    6: 100000, 7: 200000, 8: 500000, 9: 1000000, 10: 2000000,
    11: 5000000, 12: 10000000, 13: 12000000,
  };

  const businessModelMap: Record<string, string> = { "1": "b2b", "2": "b2c", "3": "d2c" };
  const priceRangeMap: Record<string, string> = { "1": "low_ticket", "2": "mid_ticket", "3": "high_ticket" };
  const goalMap: Record<string, string> = { "1": "awareness", "2": "signups", "3": "sales" };
  const authorityMap: Record<string, string> = { "1": "peer", "2": "mentor", "3": "expert" };
  const platformMap: Record<string, string> = { "1": "youtube", "2": "instagram" };

  const getCountryCode = (name: string) => {
    if (!name) return "IN";
    
    const countryMap: Record<string, string> = {
      "united states": "US",
      "united kingdom": "UK",
      "australia": "AU",
      "canada": "CA",
      "germany": "DE",
      "united arab emirates": "AE",
      "singapore": "SG",
      "france": "FR",
      "spain": "ES",
      "italy": "IT",
      "india": "IN",
      "brazil": "BR",
      "philippines": "PH",
      "indonesia": "ID"
    };

    const normalized = name.toLowerCase();
    if (countryMap[normalized]) return countryMap[normalized];
    
    return name.substring(0, 2).toUpperCase();
  };

  return {
    brand: {
      name: store.brandName || "DataLaunch",
      website: "https://datalaunch.io",
      industry: store.industry || "edtech",
      business_model: businessModelMap[store.businessModel] || "b2c",
      product_price_range: priceRangeMap[store.productPriceRange] || "high_ticket",
      core_outcome: store.pitch || "A 12-week intensive Data Science bootcamp that guarantees a job or refunds tuition.",
    },
    audience: {
      target_persona: store.targetAudience || "Junior developers and fresh CS graduates looking to switch into AI/ML roles.",
      locations: [getCountryCode(store.audienceLocation)],
      languages: ["en", "hi"],
    },
    campaign: {
      goal: goalMap[store.campaignGoal] || "signups",
      creator_authority_level: authorityMap[store.creatorAuthority] || "mentor",
      platform: store.platforms.length > 0 ? (platformMap[store.platforms[0]] || "youtube") : "youtube",
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

export default function SubmitCampaignButton() {
  const store = useCampaignStore();
  
  const handleSubmit = async () => {
    const finalPayload = transformPayload(store);
    console.log("Campaign Details Submitting:\n", JSON.stringify(finalPayload, null, 2));

    try {
      const response = await fetch("http://localhost:8000/api/campaigns/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(finalPayload)
      });
      const data = await response.json();
      console.log("Backend Response:", data);
    } catch (error) {
      console.error("Error submitting to backend:", error);
    }
  };

  return (
    <Button variant="secondary" size="lg" onClick={handleSubmit} className="w-full mt-8">
      Submit Campaign
    </Button>
  );
}
