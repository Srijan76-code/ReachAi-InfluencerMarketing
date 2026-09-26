"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRealtime } from "inngest/react";

import { getCampaignRealtimeToken } from "@/app/actions/realtime";
import { campaignChannel } from "@/inngest/channels";

type WorkflowStatusProps = {
  campaignId: string;
};

type DurableStatus = {
  run_id?: string;
  thread_id?: string;
  current_stage?: string | null;
  status?: string;
};

export default function WorkflowStatus({
  campaignId,
}: WorkflowStatusProps) {
  const { getToken } = useAuth();
  const [durableStatus, setDurableStatus] = useState<DurableStatus>({});
  const [runId, setRunId] = useState<string>();

  const channel = runId ? campaignChannel({ runId }) : undefined;
  const realtime = useRealtime({
    channel,
    topics: ["status"] as const,
    token: runId
      ? () => getCampaignRealtimeToken(campaignId, runId)
      : undefined,
    enabled: Boolean(runId),
    autoCloseOnTerminal: true,
  });

  useEffect(() => {
    let cancelled = false;

    async function reconcile() {
      const token = await getToken();
      const response = await fetch(
        `http://localhost:8000/api/campaigns/${campaignId}/status`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          cache: "no-store",
        },
      );
      if (!response.ok || cancelled) return;

      const next = (await response.json()) as DurableStatus;
      setDurableStatus(next);
      setRunId(next.run_id);
    }

    void reconcile();
    return () => {
      cancelled = true;
    };
  }, [campaignId, getToken, realtime.connectionStatus]);

  const live = realtime.messages.byTopic.status?.data;
  const stage = live?.stage ?? durableStatus.current_stage;
  const status = live?.status ?? durableStatus.status;

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
