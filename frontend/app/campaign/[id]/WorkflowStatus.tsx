"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRealtime } from "inngest/react";

import { getCampaignRealtimeToken } from "@/app/actions/realtime";
import { campaignChannel } from "@/inngest/channels";
import { useCampaignStore } from "@/store/campaignStore";

type WorkflowStatusProps = {
  campaignId: string;
};

type DurableStatus = {
  run_id?: string;
  current_stage?: string | null;
  status?: string;
};

const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export default function WorkflowStatus({
  campaignId,
}: WorkflowStatusProps) {
  const { getToken } = useAuth();
  const [durableStatus, setDurableStatus] = useState<DurableStatus>({});
  const [runId, setRunId] = useState<string>();
  const setCampaignCache = useCampaignStore((state) => state.setCampaignCache);
  const setField = useCampaignStore((state) => state.setField);

  const realtime = useRealtime({
    channel: runId ? campaignChannel({ runId }) : undefined,
    topics: ["status"] as const,
    token: runId
      ? () => getCampaignRealtimeToken(campaignId, runId)
      : undefined,
    enabled: Boolean(runId && durableStatus.status === "PENDING"),
    autoCloseOnTerminal: true,
  });

  useEffect(() => {
    if (realtime.error) {
      console.error("Inngest Realtime subscription failed:", realtime.error);
    }
  }, [realtime.error]);

  useEffect(() => {
    let cancelled = false;

    async function reconcile() {
      const token = await getToken();
      const response = await fetch(
        `${backendUrl}/api/campaigns/${campaignId}/status`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          cache: "no-store",
        },
      );
      if (!response.ok || cancelled) return;

      const next = (await response.json()) as DurableStatus;
      setDurableStatus(next);
      setRunId(next.run_id);
      setField("status", next.status ?? "CREATED");
      setField("currentStage", next.current_stage ?? null);
      setField("isGenerating", next.status === "PENDING");
    }

    void reconcile().catch((error) => {
      if (!cancelled) console.error("Unable to load campaign status:", error);
    });
    return () => {
      cancelled = true;
    };
  }, [campaignId, getToken, setField]);

  const live = realtime.messages.byTopic.status?.data;
  const stage = live?.stage ?? durableStatus.current_stage;
  const status = live?.status ?? durableStatus.status;

  useEffect(() => {
    if (!live) return;

    const normalizedStatus = live.status.toUpperCase();
    const completed = live.status === "completed";
    setField("status", normalizedStatus);
    setField("currentStage", live.stage);
    setField("stageIndex", completed ? "9/9" : null);
    setField("isGenerating", live.status === "running");
    setCampaignCache(campaignId, {
      status: normalizedStatus,
      currentStage: live.stage,
      stageIndex: completed ? "9/9" : undefined,
    });

    if (!completed) return;

    void (async () => {
      const token = await getToken();
      const response = await fetch(`${backendUrl}/api/campaigns/${campaignId}/leads`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Unable to load completed campaign leads");

      const data = (await response.json()) as { result?: unknown[] };
      const leads = data.result ?? [];
      setField("finalInfluencers", leads);
      setCampaignCache(campaignId, {
        leads,
        status: "COMPLETED",
        currentStage: "Complete",
        stageIndex: "9/9",
      });
    })().catch((error) => {
      console.error("Unable to load completed campaign leads:", error);
    });
  }, [campaignId, getToken, live, setCampaignCache, setField]);

  return (
    <section aria-live="polite" className="rounded-lg border p-4">
      <p className="text-xs text-muted-foreground">
        Workflow {realtime.connectionStatus}
      </p>
      <p className="mt-1 text-sm font-medium">
        {status === "completed"
          ? "Completed"
          : status === "failed"
            ? "Failed"
            : stage
              ? `Running: ${stage}`
              : "Waiting to start"}
      </p>
    </section>
  );
}
