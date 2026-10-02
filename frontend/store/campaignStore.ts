import { create } from "zustand";

export interface CachedCampaign {
  id: string;
  name?: string;
  details?: any;
  status?: string;
  currentStage?: string;
  stageIndex?: string;
  leads?: any[];
  savedLeads?: Record<string, any>; // map of lead identifier -> lead object
  outreachJob?: any;
}

export interface CampaignState {
  // Active Form Fields
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

  // Current Active Campaign Context
  currentCampaignId: string | null;
  status: string; // "CREATED" | "PENDING" | "COMPLETED"
  currentStage: string | null;
  stageIndex: string | null;
  isGenerating: boolean;
  isLoadingCampaign: boolean;
  finalInfluencers: any[] | null;
  latestOutreachJob: any | null;

  // Saved Leads Map (for fast lookup by id) and Array
  savedLeadsMap: Record<string, boolean>;
  savedLeadsList: any[];

  // Cache by Campaign ID for fast navigation without latency
  campaignsCache: Record<string, CachedCampaign>;

  // Actions
  setField: (field: keyof Omit<CampaignState, "setField" | "setCampaignData" | "hydrateFormFromDetails">, value: any) => void;
  setCurrentCampaignId: (id: string) => void;
  setCampaignCache: (id: string, data: Partial<CachedCampaign>) => void;
  hydrateFormFromDetails: (details: any) => void;
  loadCampaignFromCacheOrFetch: (id: string, api: any) => Promise<void>;
  toggleSaveLead: (campaignId: string, lead: any, api: any) => Promise<void>;
  fetchSavedLeads: (campaignId: string, api: any) => Promise<void>;
}

const businessModelReverseMap: Record<string, string> = { b2b: "1", b2c: "2", d2c: "3" };
const priceRangeReverseMap: Record<string, string> = { low_ticket: "1", mid_ticket: "2", high_ticket: "3" };
const goalReverseMap: Record<string, string> = { awareness: "1", signups: "2", sales: "3" };
const authorityReverseMap: Record<string, string> = { peer: "1", mentor: "2", expert: "3" };
const platformReverseMap: Record<string, string> = { youtube: "1", instagram: "2" };

export const useCampaignStore = create<CampaignState>((set, get) => ({
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

  currentCampaignId: null,
  status: "CREATED",
  currentStage: null,
  stageIndex: null,
  isGenerating: false,
  isLoadingCampaign: false,
  finalInfluencers: null,
  latestOutreachJob: null,

  savedLeadsMap: {},
  savedLeadsList: [],
  campaignsCache: {},

  setField: (field, value) => set({ [field]: value }),

  setCurrentCampaignId: (id: string) => set({ currentCampaignId: id }),

  setCampaignCache: (id: string, data: Partial<CachedCampaign>) =>
    set((state) => {
      const existing = state.campaignsCache[id] || { id };
      return {
        campaignsCache: {
          ...state.campaignsCache,
          [id]: { ...existing, ...data },
        },
      };
    }),

  hydrateFormFromDetails: (details: any) => {
    if (!details) return;

    const brand = details.brand || {};
    const audience = details.audience || {};
    const campaign = details.campaign || {};
    const constraints = details.constraints || {};

    set({
      brandName: brand.name || "",
      industry: brand.industry || "",
      businessModel: businessModelReverseMap[brand.business_model] || "1",
      productPriceRange: priceRangeReverseMap[brand.product_price_range] || "1",
      pitch: brand.core_outcome || "",
      targetAudience: audience.target_persona || "",
      audienceLocation: Array.isArray(audience.locations) && audience.locations[0] ? audience.locations[0] : "",
      campaignGoal: goalReverseMap[campaign.goal] || "1",
      creatorAuthority: authorityReverseMap[campaign.creator_authority_level] || "1",
      platforms: [platformReverseMap[campaign.platform] || "1"],
      totalBudget: campaign.budget_total ? String(campaign.budget_total) : "",
      numberOfCreators: campaign.creator_count ? [campaign.creator_count] : [3],
    });
  },

  loadCampaignFromCacheOrFetch: async (id: string, api: any) => {
    const state = get();
    set({ currentCampaignId: id });

    // Check if in cache first for instant UI response
    const cached = state.campaignsCache[id];
    if (cached) {
      if (cached.details) state.hydrateFormFromDetails(cached.details);
      if (cached.leads) set({ finalInfluencers: cached.leads });
      if (cached.status) set({ status: cached.status });
      if (cached.currentStage) set({ currentStage: cached.currentStage });
      if (cached.stageIndex) set({ stageIndex: cached.stageIndex });
      if (cached.outreachJob) set({ latestOutreachJob: cached.outreachJob });
      set({ isLoadingCampaign: false });
    } else {
      set({ isLoadingCampaign: true });
    }

    try {
      // Parallel fetch for leads + outreach in a single round-trip
      const [leadsRes, outreachRes] = await Promise.allSettled([
        api(`/api/campaigns/${id}/leads`),
        api(`/api/outreach/campaigns/${id}/latest-job`),
      ]);

      let campaignData = null;
      if (leadsRes.status === "fulfilled" && leadsRes.value?.data) {
        campaignData = leadsRes.value.data;
        if (campaignData.campaign_details) {
          get().hydrateFormFromDetails(campaignData.campaign_details);
        }
        const leads = Array.isArray(campaignData.result) ? campaignData.result : [];
        set({
          status: campaignData.status,
          currentStage: campaignData.current_stage,
          stageIndex: campaignData.stage_index,
          finalInfluencers: leads,
          isGenerating: campaignData.status === "PENDING",
        });
      }

      let outreachJob = cached?.outreachJob || null;
      if (outreachRes.status === "fulfilled" && outreachRes.value?.data) {
        outreachJob = outreachRes.value.data;
        set({ latestOutreachJob: outreachJob });
      }

      if (campaignData) {
        get().setCampaignCache(id, {
          id,
          name: campaignData.name,
          details: campaignData.campaign_details,
          status: campaignData.status,
          currentStage: campaignData.current_stage,
          stageIndex: campaignData.stage_index,
          leads: Array.isArray(campaignData.result) ? campaignData.result : [],
          outreachJob: outreachJob,
        });
      }
    } catch (err) {
      console.error("Error loading campaign:", err);
    } finally {
      set({ isLoadingCampaign: false });
    }
  },

  fetchSavedLeads: async (campaignId: string, api: any) => {
    try {
      const res = await api(`/api/saved?campaign_id=${campaignId}`);
      if (res.data && Array.isArray(res.data)) {
        const map: Record<string, boolean> = {};
        res.data.forEach((item: any) => {
          const leadId = item.lead_data?.id || item.lead_id;
          if (leadId) map[leadId] = true;
        });
        set({
          savedLeadsList: res.data,
          savedLeadsMap: map,
        });
      }
    } catch (err) {
      console.error("Error fetching saved leads:", err);
    }
  },

  toggleSaveLead: async (campaignId: string, lead: any, api: any) => {
    const leadId = lead.id;
    if (!leadId) return;

    const currentMap = { ...get().savedLeadsMap };
    const isCurrentlySaved = !!currentMap[leadId];

    // 1. Optimistic Update
    if (isCurrentlySaved) {
      delete currentMap[leadId];
      set({
        savedLeadsMap: currentMap,
        savedLeadsList: get().savedLeadsList.filter((item) => (item.lead_data?.id || item.lead_id) !== leadId),
      });
    } else {
      currentMap[leadId] = true;
      set({
        savedLeadsMap: currentMap,
        savedLeadsList: [
          ...get().savedLeadsList,
          { lead_id: leadId, campaign_id: campaignId, lead_data: lead, name: lead.title },
        ],
      });
    }

    // 2. Network sync
    try {
      if (isCurrentlySaved) {
        await api(`/api/saved/${campaignId}/${leadId}`, { method: "DELETE" });
      } else {
        await api(`/api/saved/create?campaign_id=${campaignId}`, {
          method: "POST",
          data: lead,
        });
      }
    } catch (err) {
      console.error("Error toggling saved lead:", err);
      // Revert on error
      get().fetchSavedLeads(campaignId, api);
    }
  },
}));
