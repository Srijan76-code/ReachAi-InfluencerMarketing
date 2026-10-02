"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRealtime } from "inngest/react";
import { Loader2, CheckCircle2, XCircle, AlertCircle, RotateCcw } from "lucide-react";
import { getCampaignRealtimeToken } from "@/app/actions/realtime";
import { campaignChannel } from "@/inngest/channels";
import { useCampaignStore } from "@/store/campaignStore";

const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

type DurableStatus = {
  run_id?: string;
  current_stage?: string;
  status?: string;
};

interface CampaignProgressBannerProps {
  campaignId: string;
}

export function CampaignProgressBanner({ campaignId }: CampaignProgressBannerProps) {
  const { getToken } = useAuth();
  const [durableStatus, setDurableStatus] = useState<DurableStatus>({});
  const [runId, setRunId] = useState<string>();
  const setCampaignCache = useCampaignStore((state) => state.setCampaignCache);
  const setField = useCampaignStore((state) => state.setField);

  const [isRetrying, setIsRetrying] = useState(false);

  const reconcile = useCallback(async () => {
    const token = await getToken();
    const response = await fetch(
      `${backendUrl}/api/campaigns/${campaignId}/status`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        cache: "no-store",
      }
    );
    if (!response.ok) return;
    const next = (await response.json()) as DurableStatus;
    setDurableStatus(next);
    setRunId(next.run_id);
    setField("status", next.status ?? "CREATED");
    setField("currentStage", next.current_stage ?? null);
    setField("isGenerating", next.status === "PENDING");
  }, [campaignId, getToken, setField]);

  const handleRetry = async () => {
    if (isRetrying) return;
    setIsRetrying(true);
    try {
      const token = await getToken();
      const res = await fetch(`${backendUrl}/api/campaigns/${campaignId}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        setField("status", "PENDING");
        setField("isGenerating", true);
        await reconcile();
      }
    } catch (err) {
      console.error("Failed to retry campaign generation:", err);
    } finally {
      setIsRetrying(false);
    }
  };

  useEffect(() => {
    void reconcile().catch(console.error);
  }, [reconcile]);

  const realtime = useRealtime({
    channel: runId ? campaignChannel({ runId }) : undefined,
    topics: ["status"] as const,
    token: runId ? () => getCampaignRealtimeToken(campaignId, runId) : undefined,
    enabled: Boolean(runId && durableStatus.status === "PENDING"),
    autoCloseOnTerminal: true,
  });

  const live = realtime.messages.byTopic.status?.data;
  const stage = live?.stage ?? durableStatus.current_stage;
  const status = (live?.status ?? durableStatus.status ?? "").toUpperCase();

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
      if (!response.ok) return;
      const data = (await response.json()) as { result?: unknown[] };
      const leads = data.result ?? [];
      setField("finalInfluencers", leads);
      setCampaignCache(campaignId, {
        leads,
        status: "COMPLETED",
        currentStage: "Complete",
        stageIndex: "9/9",
      });
    })().catch(console.error);
  }, [campaignId, getToken, live, setCampaignCache, setField]);

  // Don't render banner at all when completed and stage done
  if (!status || status === "COMPLETED" || stage === "completed") return null;

  return (
    <div className="mx-8 mt-4 p-4 bg-white dark:bg-[#0c0d0e] rounded-xl border border-zinc-200 dark:border-zinc-800/80 shadow-sm space-y-3">
      <div className="flex items-center justify-between gap-4">
        {/* Stage info */}
        <div className="flex items-center gap-3 min-w-0">
          {status === "PENDING" && (
            <Loader2 size={14} className="animate-spin text-blue-500 shrink-0" />
          )}
          {status === "FAILED" && (
            <XCircle size={14} className="text-rose-500 shrink-0" />
          )}
          {status === "CREATED" && (
            <AlertCircle size={14} className="text-zinc-400 shrink-0" />
          )}

          <div className="min-w-0">
            <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500 block mb-0.5">
              {status === "PENDING" ? "Generating leads" : status === "FAILED" ? "Generation failed" : "Ready to generate"}
            </span>
            {stage && status === "PENDING" && (
              <span className="text-[12px] text-zinc-700 dark:text-zinc-300 truncate block">
                {stage}
              </span>
            )}
            {status === "FAILED" && (
              <span className="text-[12px] text-rose-400">
                The AI workflow encountered an error.
              </span>
            )}
            {status === "CREATED" && (
              <span className="text-[12px] text-zinc-500">
                Submit campaign details to start lead generation.
              </span>
            )}
          </div>
        </div>

        {/* Retry button for failed */}
        {status === "FAILED" && (
          <button
            type="button"
            onClick={() => void reconcile()}
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium border border-zinc-200 dark:border-zinc-800 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none shrink-0"
          >
            <RotateCcw size={11} />
            Retry
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full h-1 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-700 rounded-full ${
            status === "FAILED"
              ? "bg-rose-500 w-full"
              : status === "PENDING"
              ? "bg-blue-500 animate-pulse w-2/3"
              : "bg-zinc-300 dark:bg-zinc-700 w-0"
          }`}
        />
      </div>
    </div>
  );
}
