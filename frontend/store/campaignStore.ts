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
  finalInfluencers: any[] | null;

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
  startCampaignStream: (id: string, token: string | null, onComplete?: (leads: any[]) => void) => () => void;
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
  finalInfluencers: null,

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
    }

    try {
      const res = await api(`/api/campaigns/${id}/details`);
      const data = res.data;
      if (data) {
        if (data.campaign_details) {
          get().hydrateFormFromDetails(data.campaign_details);
        }
        set({
          status: data.status,
          currentStage: data.current_stage,
          stageIndex: data.stage_index,
        });

        // If completed, fetch leads
        if (data.status === "COMPLETED") {
          const leadsRes = await api(`/api/campaigns/${id}/leads`);
          if (leadsRes.data && leadsRes.data.result) {
            set({
              finalInfluencers: leadsRes.data.result,
              isGenerating: false,
            });
            get().setCampaignCache(id, {
              id,
              details: data.campaign_details,
              status: data.status,
              leads: leadsRes.data.result,
            });
          }
        } else if (data.status === "PENDING") {
          set({ isGenerating: true });
        }
      }
    } catch (err) {
      console.error("Error loading campaign:", err);
    }
  },

  startCampaignStream: (id: string, token: string | null, onComplete?: (leads: any[]) => void) => {
    set({
      isGenerating: true,
      status: "PENDING",
      currentStage: "Initiating LangGraph agent...",
      stageIndex: "0/9",
      currentCampaignId: id,
    });

    const url = `http://localhost:8000/api/campaigns/${id}/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "stage") {
          set({
            currentStage: data.stage,
            stageIndex: data.stage_index,
            status: data.status,
          });
          get().setCampaignCache(id, {
            currentStage: data.stage,
            stageIndex: data.stage_index,
            status: data.status,
          });
        } else if (data.type === "complete") {
          const leads = data.leads || [];
          set({
            finalInfluencers: leads,
            isGenerating: false,
            status: "COMPLETED",
            currentStage: "Complete",
            stageIndex: "9/9",
          });
          get().setCampaignCache(id, {
            leads,
            status: "COMPLETED",
            currentStage: "Complete",
          });
          eventSource.close();
          if (onComplete) onComplete(leads);
        } else if (data.type === "error") {
          console.error("Stream reported error:", data.message);
          set({ isGenerating: false });
          eventSource.close();
        }
      } catch (err) {
        console.warn("Non-JSON SSE message or parse error:", event.data);
      }
    };

    eventSource.onerror = (err) => {
      console.warn("SSE connection closed or error:", err);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
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
