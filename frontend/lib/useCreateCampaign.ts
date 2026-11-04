"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";

/** Creates an empty campaign and opens its brief. Used by the navbar's "New campaign" button. */
export function useCreateCampaign() {
  const api = useApi();
  const router = useRouter();
  const [creating, setCreating] = useState(false);

  const create = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const res = await api("/api/campaigns/create", { method: "POST" });
      if (res.data?.campaign_id) router.push(`/campaign/${res.data.campaign_id}/details`);
    } catch (err) {
      console.error("Error creating campaign:", err);
      window.alert(err instanceof Error ? err.message : "Couldn't create a campaign. Refresh the page and sign in again.");
    } finally {
      setCreating(false);
    }
  };

  return { create, creating };
}
