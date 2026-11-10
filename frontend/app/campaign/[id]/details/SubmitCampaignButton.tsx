"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Loader2, Sparkles } from "lucide-react";
import { useCampaignStore, CampaignState } from "@/store/campaignStore";
import { countryCode, languagesFor } from "@/lib/countries";
import { stepToSubscribers } from "@/lib/creatorSize";

const businessModelMap: Record<string, string> = { "1": "b2b", "2": "b2c", "3": "d2c" };
const priceRangeMap: Record<string, string> = { "1": "low_ticket", "2": "mid_ticket", "3": "high_ticket" };
const goalMap: Record<string, string> = { "1": "awareness", "2": "signups", "3": "sales" };
const authorityMap: Record<string, string> = { "1": "peer", "2": "mentor", "3": "expert" };

/** What's missing before a run can start (empty list = ready). */
export function missingFields(store: CampaignState): string[] {
  const missing: string[] = [];
  if (!store.brandName.trim()) missing.push("brand name");
  if (!store.pitch.trim()) missing.push("what you sell");
  if (!store.targetAudience.trim()) missing.push("target audience");
  if (!countryCode(store.audienceLocation)) missing.push("audience location");
  return missing;
}

export function transformPayload(store: CampaignState) {
  const country = countryCode(store.audienceLocation);
  const countries = country ? [country] : [];
  return {
    brand: {
      name: store.brandName.trim(),
      industry: store.industry || "other",
      business_model: businessModelMap[store.businessModel] || "b2c",
      product_price_range: priceRangeMap[store.productPriceRange] || "mid_ticket",
      core_outcome: store.pitch.trim(),
    },
    audience: {
      target_persona: store.targetAudience.trim(),
      locations: countries,
      languages: languagesFor(country),
    },
    campaign: {
      goal: goalMap[store.campaignGoal] || "signups",
      creator_authority_level: authorityMap[store.creatorAuthority] || "peer",
      platforms: store.platforms, // empty = ReachAI chooses (preset for the business type + a quick AI check)
      budget_total: parseInt(store.totalBudget) || 5000,
      creator_count: store.numberOfCreators[0] || 5,
    },
    constraints: {
      min_subscribers: stepToSubscribers(store.creatorSize[0], 10000),
      max_subscribers: stepToSubscribers(store.creatorSize[1], 500000),
      target_countries: countries,
      exclude_kids_content: true,
    },
  };
}

export default function SubmitCampaignButton({ id }: { id: string }) {
  const store = useCampaignStore();
  const router = useRouter();
  const { getToken } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (isSubmitting) return;
    const missing = missingFields(store);
    if (missing.length) {
      setError(`Please fill in: ${missing.join(", ")}.`);
      return;
    }
    setError(null);
    const finalPayload = transformPayload(store);
    setIsSubmitting(true);
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
      setIsSubmitting(false);
      setError("Couldn't start the search. Please try again.");
    }
  };

  return (
    <div className="space-y-2">
    {error && <p role="alert" className="text-[12px] text-rose-500">{error}</p>}
    <button
      type="button"
      onClick={handleSubmit}
      disabled={isSubmitting}
      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-[13px] font-medium bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 rounded-lg hover:bg-zinc-800 dark:hover:bg-zinc-100 transition-colors disabled:opacity-50 shadow-sm"
    >
      {isSubmitting ? (
        <>
          <Loader2 size={14} className="animate-spin" />
          Starting campaign...
        </>
      ) : (
        <>
          <Sparkles size={14} />
          Find Creators
        </>
      )}
    </button>
    </div>
  );
}

