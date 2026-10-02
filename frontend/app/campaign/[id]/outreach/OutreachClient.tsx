"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { useRealtime } from "inngest/react";
import {
  Send,
  Sparkles,
  Mail,
  Instagram,
  Twitter,
  Linkedin,
  Copy,
  Check,
  ExternalLink,
  Clock,
  Loader2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Download,
  Users,
  Layers,
  ChevronRight,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useApi } from "@/lib/api";
import { useCampaignStore } from "@/store/campaignStore";
import { outreachChannel } from "@/inngest/channels";
import { getOutreachRealtimeToken } from "@/app/actions/realtime";
import { ExportPitchesDialog } from "@/components/ExportPitchesDialog";
import type { Influencer } from "@/data/influencerList";

interface OutreachPitchItem {
  pitch_id: string;
  creator_id: string;
  status: "PENDING" | "GENERATING" | "COMPLETED" | "NEEDS_REVIEW" | "FAILED";
  available_channels?: string[];
  pitch_bundle?: {
    creator_id?: string;
    pitch_angle?: string;
    personalization?: Array<{ evidence_id: string; reason: string }>;
    email?: { subject: string; body: string };
    instagram?: { body: string };
    twitter?: { body: string };
    linkedin?: { body: string };
  };
  validation_errors?: string[];
  repair_count?: number;
}

interface OutreachJobDetail {
  outreach_job_id: string;
  campaign_id: string;
  status: "CREATED" | "PENDING" | "COMPLETED" | "FAILED";
  run_id?: string;
  thread_id?: string;
  collaboration_type?: string;
  deliverables?: string[];
  selected_creator_ids: string[];
  pitches: OutreachPitchItem[];
  pitch_pack?: any;
  generation_stats?: {
    creator_count?: number;
    successful_count?: number;
    needs_review_count?: number;
    reachable_channel_count?: number;
    repair_count?: number;
  };
  error_message?: string;
}

const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export default function OutreachClient({
  campaignId,
  initialJobId,
}: {
  campaignId: string;
  initialJobId?: string;
}) {
  const api = useApi();
  const { getToken } = useAuth();

  const finalInfluencers = useCampaignStore((state) => state.finalInfluencers);
  const cachedJob = useCampaignStore(
    (state) => state.campaignsCache[campaignId]?.outreachJob || state.latestOutreachJob
  );
  const setCampaignCache = useCampaignStore((state) => state.setCampaignCache);
  const setField = useCampaignStore((state) => state.setField);

  const [job, setJob] = useState<OutreachJobDetail | null>(() => cachedJob || null);
  const [isLoading, setIsLoading] = useState(() => !cachedJob);
  const [activePitch, setActivePitch] = useState<OutreachPitchItem | null>(null);
  const [activeTab, setActiveTab] = useState<"email" | "instagram" | "twitter" | "linkedin">("email");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    if (cachedJob && !job) {
      setJob(cachedJob);
      setIsLoading(false);
    }
  }, [cachedJob, job]);

  // Map influencers by ID
  const influencersMap = useMemo(() => {
    const map = new Map<string, Influencer>();
    for (const lead of finalInfluencers || []) {
      if (lead.id) map.set(lead.id, lead);
    }
    return map;
  }, [finalInfluencers]);

  // Load Job
  const fetchJob = useCallback(async (jobId?: string) => {
    try {
      const endpoint = jobId
        ? `/api/outreach/jobs/${jobId}`
        : `/api/outreach/campaigns/${campaignId}/latest-job`;

      const res = await api(endpoint);
      if (res?.data) {
        setJob(res.data);
        setCampaignCache(campaignId, { outreachJob: res.data });
        setField("latestOutreachJob", res.data);
      }
    } catch (err) {
      console.warn("No active outreach job found:", err);
    } finally {
      setIsLoading(false);
    }
  }, [api, campaignId, setCampaignCache, setField]);

  const handleRetry = async () => {
    if (!job?.outreach_job_id || isRetrying) return;
    setIsRetrying(true);
    try {
      await api(`/api/outreach/jobs/${job.outreach_job_id}/start`, {
        method: "POST",
      });
      setJob((prev) =>
        prev
          ? {
              ...prev,
              status: "PENDING",
              error_message: undefined,
            }
          : prev
      );
      await fetchJob(job.outreach_job_id);
    } catch (err) {
      console.error("Failed to retry outreach job:", err);
    } finally {
      setIsRetrying(false);
    }
  };

  const handleSync = async () => {
    if (!job?.outreach_job_id || isSyncing) return;
    setIsSyncing(true);
    try {
      await fetchJob(job.outreach_job_id);
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchJob(initialJobId);
  }, [fetchJob, initialJobId]);

  // Inngest Realtime Hook
  const runId = job?.run_id;
  const isJobRunning = job?.status === "PENDING";

  const realtime = useRealtime({
    channel: runId ? outreachChannel({ runId }) : undefined,
    topics: ["status"] as const,
    token: runId && job?.outreach_job_id
      ? () => getOutreachRealtimeToken(job.outreach_job_id, runId)
      : undefined,
    enabled: Boolean(runId && isJobRunning),
    autoCloseOnTerminal: true,
  });

  // Handle Realtime Messages
  const liveUpdate = realtime.messages.byTopic.status?.data;
  useEffect(() => {
    if (!liveUpdate || !job) return;

    if (liveUpdate.stage === "creator_pitch_generating" && liveUpdate.creator_id) {
      setJob((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          pitches: prev.pitches.map((p) =>
            p.creator_id === liveUpdate.creator_id ? { ...p, status: "GENERATING" } : p
          ),
        };
      });
    } else if (liveUpdate.stage === "creator_pitch_completed" && liveUpdate.creator_id) {
      const pitchStatus = (liveUpdate.pitch_status || "completed").toUpperCase() as any;
      setJob((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          pitches: prev.pitches.map((p) =>
            p.creator_id === liveUpdate.creator_id ? { ...p, status: pitchStatus } : p
          ),
        };
      });
    } else if (liveUpdate.status === "completed" || liveUpdate.stage === "completed") {
      fetchJob(job.outreach_job_id);
    }
  }, [liveUpdate, job?.outreach_job_id, fetchJob]);

  // Polling fallback when running
  useEffect(() => {
    if (!job || job.status !== "PENDING") return;
    const interval = setInterval(() => {
      fetchJob(job.outreach_job_id);
    }, 4000);
    return () => clearInterval(interval);
  }, [job?.status, job?.outreach_job_id, fetchJob]);

  // Copy with feedback
  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  // Export pitch pack JSON/CSV
  const handleExportPitchPack = () => {
    if (!job || !job.pitches) return;
    const rows = job.pitches.map((p) => {
      const lead = influencersMap.get(p.creator_id);
      return {
        creator_name: lead?.title || p.creator_id,
        country: lead?.country || "",
        email: lead?.socials?.email || "",
        instagram: lead?.socials?.instagram || "",
        twitter: lead?.socials?.twitter || "",
        pitch_angle: p.pitch_bundle?.pitch_angle || "",
        email_subject: p.pitch_bundle?.email?.subject || "",
        email_body: p.pitch_bundle?.email?.body || "",
        instagram_pitch: p.pitch_bundle?.instagram?.body || "",
        twitter_pitch: p.pitch_bundle?.twitter?.body || "",
        linkedin_pitch: p.pitch_bundle?.linkedin?.body || "",
        status: p.status,
      };
    });

    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `outreach_pitches_${campaignId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Progress stats
  const totalPitches = job?.pitches?.length || 0;
  const completedPitches = job?.pitches?.filter(
    (p) => p.status === "COMPLETED" || p.status === "NEEDS_REVIEW"
  ).length || 0;
  const progressPercent = totalPitches > 0 ? Math.round((completedPitches / totalPitches) * 100) : 0;

  // Build export-ready pitch items for ExportPitchesDialog
  const exportPitchItems = useMemo(() => {
    if (!job?.pitches) return [];
    return job.pitches
      .filter((p) => p.status === "COMPLETED" || p.status === "NEEDS_REVIEW")
      .map((p) => {
        const lead = influencersMap.get(p.creator_id);
        return {
          creator_name: lead?.title || p.creator_id,
          email: lead?.socials?.email || "",
          country: lead?.country || "",
          instagram_handle: lead?.socials?.instagram || "",
          twitter_handle: lead?.socials?.twitter || "",
          linkedin_handle: lead?.socials?.linkedin || "",
          pitch_angle: p.pitch_bundle?.pitch_angle || "",
          subject: p.pitch_bundle?.email?.subject || "",
          email_body: p.pitch_bundle?.email?.body || "",
          instagram_pitch: p.pitch_bundle?.instagram?.body || "",
          twitter_pitch: p.pitch_bundle?.twitter?.body || "",
          linkedin_pitch: p.pitch_bundle?.linkedin?.body || "",
        };
      });
  }, [job?.pitches, influencersMap]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] flex items-center justify-center p-8">
        <div className="flex items-center gap-3 text-zinc-500 text-xs">
          <Loader2 size={16} className="animate-spin text-zinc-400" />
          <span>Loading outreach...</span>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] text-zinc-600 dark:text-zinc-400 p-8 font-sans">
        <div className="max-w-4xl mx-auto mt-16 text-center space-y-4 p-12 bg-white dark:bg-[#0c0d0e] rounded-xl border border-zinc-200 dark:border-zinc-800">
          <div className="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center mx-auto">
            <Send size={20} />
          </div>
          <h2 className="text-[17px] font-medium text-zinc-900 dark:text-zinc-100">
            No Outreach Campaigns Created Yet
          </h2>
          <p className="text-[13px] text-zinc-500 max-w-md mx-auto">
            Select high-affinity creators from the Leads tab and click &quot;Start Outreach&quot; to automatically synthesize hyper-personalized email &amp; DM pitch bundles.
          </p>
          <div className="pt-2">
            <Link
              href={`/campaign/${campaignId}/leads`}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 rounded-md hover:bg-zinc-800 dark:hover:bg-zinc-100 transition-colors shadow-sm"
            >
              <Users size={13} />
              Browse Qualified Leads
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] text-zinc-600 dark:text-zinc-400 p-8 font-sans selection:bg-blue-500/30">
        <div className="max-w-7xl mx-auto space-y-5">
          {/* Header Bar */}
          <div className="flex items-center justify-between px-1 py-2">
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <h1 className="text-[16px] font-medium text-zinc-900 dark:text-zinc-100 tracking-tight">
                  Creator outreach sequences
                </h1>
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-full font-medium border ${
                    job.status === "COMPLETED"
                      ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                      : job.status === "PENDING"
                      ? "bg-blue-500/10 text-blue-500 border-blue-500/20 animate-pulse"
                      : job.status === "FAILED"
                      ? "bg-rose-500/10 text-rose-500 border-rose-500/20"
                      : "bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border-transparent"
                  }`}
                >
                  {job.status === "COMPLETED"
                    ? "Batch complete"
                    : job.status === "PENDING"
                    ? "Generating pitches..."
                    : job.status === "FAILED"
                    ? "Failed"
                    : job.status.toLowerCase()}
                </span>
              </div>
              <p className="text-[12px] text-zinc-500">
                AI personalized pitches across email, Instagram, and Twitter.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSync}
                disabled={isSyncing}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors disabled:opacity-50"
                title="Refresh from Database"
              >
                <RefreshCw size={13} className={isSyncing || isJobRunning ? "animate-spin" : ""} />
                {isSyncing ? "Syncing..." : "Sync"}
              </button>

              <ExportPitchesDialog
                pitches={exportPitchItems}
                campaignId={campaignId}
                completedCount={completedPitches}
              />
            </div>
          </div>

          {/* Progress / Context Banner */}
          <div className="p-4 bg-white dark:bg-[#0c0d0e] rounded-xl border border-zinc-200 dark:border-zinc-800/80 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-5">
                <div>
                  <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500 block mb-0.5">
                    Progress
                  </span>
                  <span className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">
                    {completedPitches} / {totalPitches} pitches ready
                  </span>
                </div>

                {job.collaboration_type && (
                  <>
                    <div className="h-6 w-[1px] bg-zinc-200 dark:bg-zinc-800" />
                    <div>
                      <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500 block mb-0.5">
                        Format
                      </span>
                      <span className="text-[13px] font-medium text-zinc-800 dark:text-zinc-200 capitalize">
                        {job.collaboration_type.replace(/_/g, " ")}
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* Status indicator — correct for all states */}
              <div className="flex items-center gap-2">
                {job.status === "PENDING" ? (
                  <span className="flex items-center gap-1.5 text-blue-500 text-[12px]">
                    <Loader2 size={13} className="animate-spin" />
                    Generating pitches in parallel...
                  </span>
                ) : job.status === "FAILED" ? (
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1.5 text-rose-500 text-[12px]">
                      <XCircle size={13} />
                      Generation failed
                    </span>
                    <button
                      type="button"
                      onClick={handleRetry}
                      disabled={isRetrying}
                      className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium border border-zinc-200 dark:border-zinc-800 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors focus:outline-none disabled:opacity-50"
                    >
                      <RotateCcw size={11} className={isRetrying ? "animate-spin" : ""} />
                      {isRetrying ? "Retrying..." : "Retry"}
                    </button>
                  </div>
                ) : job.status === "COMPLETED" && completedPitches === 0 ? (
                  <span className="flex items-center gap-1.5 text-zinc-400 text-[12px]">
                    <AlertCircle size={13} />
                    No pitches completed
                  </span>
                ) : job.status === "COMPLETED" ? (
                  <span className="flex items-center gap-1.5 text-emerald-500 text-[12px]">
                    <CheckCircle2 size={13} />
                    {completedPitches === totalPitches
                      ? "All pitches ready"
                      : `${completedPitches} of ${totalPitches} pitches ready`}
                  </span>
                ) : null}
              </div>
            </div>

            {/* Progress bar — red on failure, blue while running, green when done */}
            <div className="w-full h-1 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 rounded-full ${
                  job.status === "FAILED"
                    ? "bg-rose-500"
                    : job.status === "PENDING"
                    ? "bg-blue-500"
                    : "bg-emerald-500"
                }`}
                style={{ width: job.status === "FAILED" ? "100%" : `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Pitch Rows List */}
          <div className="flex flex-col gap-2">
            {job.pitches.map((pitch, index) => {
              const lead = influencersMap.get(pitch.creator_id);
              const title = lead?.title || pitch.creator_id;
              const country = lead?.country?.toUpperCase() || "GLOBAL";
              const isReady = pitch.status === "COMPLETED";
              const isNeedsReview = pitch.status === "NEEDS_REVIEW";
              const isFailed = pitch.status === "FAILED" || (job.status === "FAILED" && pitch.status === "PENDING");
              const isGenerating = pitch.status === "GENERATING" || (job.status === "PENDING" && pitch.status === "PENDING");

              return (
                <div
                  key={pitch.pitch_id}
                  onClick={() => {
                    if (isReady || isNeedsReview || pitch.pitch_bundle) {
                      setActivePitch(pitch);
                    }
                  }}
                  className={`group flex items-center justify-between px-5 py-3.5 rounded-lg border transition-all cursor-pointer text-[13px] ${
                    isReady
                      ? "bg-white dark:bg-[#0c0d0e] border-zinc-200/70 dark:border-zinc-800/80 hover:border-zinc-300 dark:hover:border-zinc-700"
                      : "bg-zinc-50/60 dark:bg-[#0c0d0e]/60 border-zinc-200/40 dark:border-zinc-800/40"
                  }`}
                >
                  {/* Left: Rank & Creator Details */}
                  <div className="flex items-center gap-4 min-w-[280px]">
                    <span className="text-[11px] font-mono text-zinc-400 w-5">
                      {String(index + 1).padStart(2, "0")}
                    </span>

                    <div className="w-8 h-8 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center font-medium text-xs text-zinc-900 dark:text-zinc-100">
                      {title.charAt(0).toUpperCase()}
                    </div>

                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-zinc-900 dark:text-zinc-100">
                          {title}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500 font-mono">
                          {country}
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-400 truncate max-w-[260px]">
                        {lead?.description || "YouTube Creator Lead"}
                      </p>
                    </div>
                  </div>

                  {/* Pitch Angle Preview (if ready) */}
                  <div className="flex-1 px-6 hidden md:block">
                    {pitch.pitch_bundle?.pitch_angle ? (
                      <p className="text-[12px] text-zinc-600 dark:text-zinc-400 italic truncate max-w-[420px]">
                        &quot;{pitch.pitch_bundle.pitch_angle}&quot;
                      </p>
                    ) : isGenerating ? (
                      <span className="text-[11px] text-zinc-400 animate-pulse">
                        Analyzing transcripts &amp; synthesizing pitch...
                      </span>
                    ) : isFailed ? (
                      <span className="text-[11px] text-rose-400">Generation failed</span>
                    ) : (
                      <span className="text-[11px] text-zinc-400">In queue</span>
                    )}
                  </div>

                  {/* Channel Badges */}
                  <div className="flex items-center gap-1.5 px-3">
                    {pitch.available_channels?.includes("email") && (
                      <span className="p-1 rounded bg-zinc-100 dark:bg-zinc-800/70 text-zinc-600 dark:text-zinc-300" title="Email Pitch Available">
                        <Mail size={13} />
                      </span>
                    )}
                    {pitch.available_channels?.includes("instagram") && (
                      <span className="p-1 rounded bg-zinc-100 dark:bg-zinc-800/70 text-zinc-600 dark:text-zinc-300" title="Instagram DM Ready">
                        <Instagram size={13} />
                      </span>
                    )}
                    {pitch.available_channels?.includes("twitter") && (
                      <span className="p-1 rounded bg-zinc-100 dark:bg-zinc-800/70 text-zinc-600 dark:text-zinc-300" title="X / Twitter DM Ready">
                        <Twitter size={13} />
                      </span>
                    )}
                    {pitch.available_channels?.includes("linkedin") && (
                      <span className="p-1 rounded bg-zinc-100 dark:bg-zinc-800/70 text-zinc-600 dark:text-zinc-300" title="LinkedIn Note Ready">
                        <Linkedin size={13} />
                      </span>
                    )}
                  </div>

                  {/* Right Status & Action */}
                  <div className="flex items-center gap-3 w-40 justify-end">
                    {isReady && (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-500 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                        <Check size={11} className="stroke-[3]" />
                        Pitch Ready
                      </span>
                    )}
                    {isNeedsReview && (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-amber-500 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20">
                        <AlertCircle size={11} />
                        Needs Review
                      </span>
                    )}
                    {isGenerating && (
                      <span className="flex items-center gap-1.5 text-[11px] font-medium text-blue-500 bg-blue-500/10 px-2.5 py-1 rounded-full border border-blue-500/20 animate-pulse">
                        <Loader2 size={11} className="animate-spin" />
                        Generating
                      </span>
                    )}
                    {isFailed && (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-rose-500 bg-rose-500/10 px-2.5 py-1 rounded-full border border-rose-500/20">
                        <XCircle size={11} />
                        Failed
                      </span>
                    )}
                    {!isReady && !isNeedsReview && !isGenerating && !isFailed && (
                      <span className="flex items-center gap-1 text-[11px] text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-2.5 py-1 rounded-full">
                        <Clock size={11} />
                        Queued
                      </span>
                    )}

                    <ChevronRight size={14} className="text-zinc-400 group-hover:text-zinc-700 dark:group-hover:text-zinc-200 transition-colors" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Pitch Detail Sheet (Slide-over) */}
        <Sheet open={Boolean(activePitch)} onOpenChange={(open) => !open && setActivePitch(null)}>
          <SheetContent side="right" className="w-full sm:max-w-xl p-0 bg-white dark:bg-[#0c0d0e] border-l border-zinc-200 dark:border-zinc-800 overflow-y-auto flex flex-col font-sans">
            {activePitch && (() => {
              const lead = influencersMap.get(activePitch.creator_id);
              const bundle = activePitch.pitch_bundle;
              const email = bundle?.email;
              const instagram = bundle?.instagram;
              const twitter = bundle?.twitter;
              const linkedin = bundle?.linkedin;
              const leadEmail = lead?.socials?.email;

              return (
                <div className="flex flex-col h-full">
                  {/* Sheet Header */}
                  <div className="p-6 border-b border-zinc-200 dark:border-white/5 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/80 flex items-center justify-center text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                          {(lead?.title || activePitch.creator_id).charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <SheetTitle className="text-[16px] font-semibold text-zinc-900 dark:text-zinc-100">
                            {lead?.title || "Creator Pitch"}
                          </SheetTitle>
                          <span className="text-[12px] text-zinc-500">
                            Personalized Pitch Pack • {activePitch.status}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Pitch Angle Callout */}
                    {bundle?.pitch_angle && (
                      <div className="p-3 bg-zinc-50 dark:bg-zinc-900/60 rounded-lg border border-zinc-200/80 dark:border-white/5 space-y-1">
                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                          <Sparkles size={12} />
                          Personalization Angle
                        </div>
                        <p className="text-[12px] text-zinc-700 dark:text-zinc-300">
                          {bundle.pitch_angle}
                        </p>
                      </div>
                    )}

                    {/* Cited Evidence Tags */}
                    {bundle?.personalization && bundle.personalization.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-400">
                          Grounded Creator Evidence:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {bundle.personalization.map((ev, i) => (
                            <div
                              key={i}
                              className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800/80 text-[11px] text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700/50"
                            >
                              <span className="font-mono text-zinc-400 mr-1">#{ev.evidence_id}</span>
                              <span>{ev.reason}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Channel Tab Selector */}
                  <div className="flex items-center border-b border-zinc-200 dark:border-white/5 px-6 gap-2 pt-2 bg-zinc-50/50 dark:bg-[#0c0d0e]">
                    <button
                      type="button"
                      onClick={() => setActiveTab("email")}
                      className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                        activeTab === "email"
                          ? "border-zinc-900 dark:border-white text-zinc-900 dark:text-zinc-100"
                          : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300"
                      }`}
                    >
                      <Mail size={13} />
                      Email Draft
                    </button>

                    {instagram && (
                      <button
                        type="button"
                        onClick={() => setActiveTab("instagram")}
                        className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                          activeTab === "instagram"
                            ? "border-zinc-900 dark:border-white text-zinc-900 dark:text-zinc-100"
                            : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300"
                        }`}
                      >
                        <Instagram size={13} />
                        Instagram DM
                      </button>
                    )}

                    {twitter && (
                      <button
                        type="button"
                        onClick={() => setActiveTab("twitter")}
                        className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                          activeTab === "twitter"
                            ? "border-zinc-900 dark:border-white text-zinc-900 dark:text-zinc-100"
                            : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300"
                        }`}
                      >
                        <Twitter size={13} />
                        Twitter / X DM
                      </button>
                    )}

                    {linkedin && (
                      <button
                        type="button"
                        onClick={() => setActiveTab("linkedin")}
                        className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                          activeTab === "linkedin"
                            ? "border-zinc-900 dark:border-white text-zinc-900 dark:text-zinc-100"
                            : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300"
                        }`}
                      >
                        <Linkedin size={13} />
                        LinkedIn
                      </button>
                    )}
                  </div>

                  {/* Channel Content Body */}
                  <div className="flex-1 p-6 space-y-4 overflow-y-auto">
                    {/* EMAIL TAB */}
                    {activeTab === "email" && (
                      <div className="space-y-4">
                        {email ? (
                          <>
                            {/* Subject */}
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                                  Subject Line
                                </span>
                                <button
                                  type="button"
                                  onClick={() => handleCopy(email.subject, "subj")}
                                  className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                                >
                                  {copiedKey === "subj" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                                  {copiedKey === "subj" ? "Copied" : "Copy"}
                                </button>
                              </div>
                              <div className="p-3 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 text-[13px] font-medium text-zinc-900 dark:text-zinc-100 select-all">
                                {email.subject}
                              </div>
                            </div>

                            {/* Body */}
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                                  Email Body
                                </span>
                                <button
                                  type="button"
                                  onClick={() => handleCopy(email.body, "body")}
                                  className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                                >
                                  {copiedKey === "body" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                                  {copiedKey === "body" ? "Copied" : "Copy"}
                                </button>
                              </div>
                              <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 text-[13px] text-zinc-700 dark:text-zinc-200 whitespace-pre-line leading-relaxed font-sans select-all">
                                {email.body}
                              </div>
                            </div>

                            {/* Direct Mailto */}
                            {leadEmail && (
                              <div className="pt-2">
                                <a
                                  href={`mailto:${leadEmail}?subject=${encodeURIComponent(
                                    email.subject
                                  )}&body=${encodeURIComponent(email.body)}`}
                                  className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 rounded-md hover:bg-zinc-800 dark:hover:bg-zinc-100 transition-colors shadow-sm"
                                >
                                  <ExternalLink size={13} />
                                  Open Draft in Mail App ({leadEmail})
                                </a>
                              </div>
                            )}
                          </>
                        ) : (
                          <p className="text-xs text-zinc-400">
                            No email channel detected for this creator.
                          </p>
                        )}
                      </div>
                    )}

                    {/* INSTAGRAM TAB */}
                    {activeTab === "instagram" && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                            Instagram DM Pitch
                          </span>
                          <button
                            type="button"
                            onClick={() => handleCopy(instagram?.body || "", "ig")}
                            className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                          >
                            {copiedKey === "ig" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                            {copiedKey === "ig" ? "Copied" : "Copy DM"}
                          </button>
                        </div>
                        <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 text-[13px] text-zinc-700 dark:text-zinc-200 whitespace-pre-line leading-relaxed select-all">
                          {instagram?.body}
                        </div>
                        {lead?.socials?.instagram && (
                          <a
                            href={lead.socials.instagram}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-400 hover:underline pt-1"
                          >
                            <ExternalLink size={12} />
                            Open Instagram Profile ({lead.socials.instagram})
                          </a>
                        )}
                      </div>
                    )}

                    {/* TWITTER TAB */}
                    {activeTab === "twitter" && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                            X / Twitter Direct Message
                          </span>
                          <button
                            type="button"
                            onClick={() => handleCopy(twitter?.body || "", "tw")}
                            className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                          >
                            {copiedKey === "tw" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                            {copiedKey === "tw" ? "Copied" : "Copy DM"}
                          </button>
                        </div>
                        <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 text-[13px] text-zinc-700 dark:text-zinc-200 whitespace-pre-line leading-relaxed select-all">
                          {twitter?.body}
                        </div>
                        {lead?.socials?.twitter && (
                          <a
                            href={lead.socials.twitter}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-400 hover:underline pt-1"
                          >
                            <ExternalLink size={12} />
                            Open X Profile ({lead.socials.twitter})
                          </a>
                        )}
                      </div>
                    )}

                    {/* LINKEDIN TAB */}
                    {activeTab === "linkedin" && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                            LinkedIn Connection Note
                          </span>
                          <button
                            type="button"
                            onClick={() => handleCopy(linkedin?.body || "", "li")}
                            className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                          >
                            {copiedKey === "li" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                            {copiedKey === "li" ? "Copied" : "Copy"}
                          </button>
                        </div>
                        <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 text-[13px] text-zinc-700 dark:text-zinc-200 whitespace-pre-line leading-relaxed select-all">
                          {linkedin?.body}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}
          </SheetContent>
        </Sheet>
      </div>
    </TooltipProvider>
  );
}
