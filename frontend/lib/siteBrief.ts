import { useCampaignStore } from "@/store/campaignStore";

/** Fields the website filled and Jev confirmed are hidden from the brief form until "Show all fields" (F1.24). */
export function useHiddenBySite(field: string): boolean {
  return useCampaignStore((s) => !!s.site && !s.showAllFields && s.site.confirmed.includes(field));
}

export const SITE_FIELD_LABELS: Record<string, string> = {
  brand_name: "Brand name",
  core_outcome: "What you sell",
  target_persona: "Who buys",
  industry: "Industry",
  business_model: "Business model",
  price_range: "Price range",
  competitors: "Competitors",
};
