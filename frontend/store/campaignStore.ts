import { create } from "zustand";

export interface CampaignState {
  brandName: string;
  industry: string;
  businessModel: string;
  productPriceRange: string;
  campaignGoal: string;
  creatorAuthority: string;
  platforms: string[];
  audienceLocation: string;
  pitch: string;
  targetAudience: string;
  creatorSize: number[];
  totalBudget: string;
  numberOfCreators: number[];
  
  // API Integration states
  isGenerating: boolean;
  finalInfluencers: any[] | null;
  
  setField: (field: keyof Omit<CampaignState, "setField">, value: any) => void;
}

export const useCampaignStore = create<CampaignState>((set) => ({
  brandName: "",
  industry: "",
  businessModel: "1",
  productPriceRange: "1",
  campaignGoal: "1",
  creatorAuthority: "1",
  platforms: ["1"], // YouTube default
  audienceLocation: "",
  pitch: "",
  targetAudience: "",
  creatorSize: [3, 8],
  totalBudget: "",
  numberOfCreators: [3],
  isGenerating: false,
  finalInfluencers: null,
  setField: (field, value) => set({ [field]: value }),
}));
