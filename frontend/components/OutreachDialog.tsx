"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Send, Sparkles, Check, Plus, X, Layers, Gift, Link2, Video, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";
import { useApi } from "@/lib/api";
import type { Influencer } from "@/data/influencerList";

interface OutreachDialogProps {
  campaignId: string;
  influencers: Influencer[];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: React.ReactNode;
}

const COLLABORATION_OPTIONS = [
  {
    id: "sponsored_video",
    label: "Sponsored Video",
    desc: "60-90s dedicated integration or deep feature highlight in standard upload.",
    icon: Video,
  },
  {
    id: "dedicated_review",
    label: "Dedicated Review",
    desc: "Full dedicated video reviewing the product experience thoroughly.",
    icon: Layers,
  },
  {
    id: "affiliate",
    label: "Affiliate & Performance",
    desc: "Commission-backed partnership with tracking link and discount code.",
    icon: Link2,
  },
  {
    id: "gifting",
    label: "Product Gifting / Seeding",
    desc: "Free product exchange for honest creator review or social shoutout.",
    icon: Gift,
  },
];

const DEFAULT_DELIVERABLES = [
  "1x 60s Mid-roll Integration",
  "Pinned Comment & Top Description Link",
  "30-day Organic & Paid Usage Rights",
  "Cross-post to Instagram Story or X",
];

export function OutreachDialog({
  campaignId,
  influencers,
  open: controlledOpen,
  onOpenChange: setControlledOpen,
  trigger,
}: OutreachDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;
  const setOpen = isControlled ? setControlledOpen! : setInternalOpen;

  const router = useRouter();
  const api = useApi();

  const [collaborationType, setCollaborationType] = useState<string>("sponsored_video");
  const [selectedDeliverables, setSelectedDeliverables] = useState<string[]>([
    "1x 60s Mid-roll Integration",
    "Pinned Comment & Top Description Link",
  ]);
  const [customDeliverable, setCustomDeliverable] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleDeliverable = (item: string) => {
    setSelectedDeliverables((prev) =>
      prev.includes(item) ? prev.filter((d) => d !== item) : [...prev, item]
    );
  };

  const addCustomDeliverable = () => {
    const trimmed = customDeliverable.trim();
    if (!trimmed) return;
    if (!selectedDeliverables.includes(trimmed)) {
      setSelectedDeliverables((prev) => [...prev, trimmed]);
    }
    setCustomDeliverable("");
  };

  const handleStartOutreach = async () => {
    if (influencers.length === 0) return;
    setIsSubmitting(true);
    setError(null);

    const creatorIds = influencers.map((inf) => inf.id);

    try {
      const res = await api(`/api/outreach/campaigns/${campaignId}/jobs`, {
        method: "POST",
        body: JSON.stringify({
          selected_creator_ids: creatorIds,
          collaboration_type: collaborationType,
          deliverables: selectedDeliverables,
          auto_start: true,
        }),
      });

      const jobId = res?.data?.outreach_job_id;
      setOpen(false);
      router.push(`/campaign/${campaignId}/outreach${jobId ? `?job_id=${jobId}` : ""}`);
    } catch (err: any) {
      console.error("Outreach start failed:", err);
      setError(err?.message || "Failed to start outreach job. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger ? (
        <DialogTrigger asChild>{trigger}</DialogTrigger>
      ) : (
        <DialogTrigger asChild>
          <button
            type="button"
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 rounded-md hover:bg-zinc-800 dark:hover:bg-zinc-100 transition-colors shadow-sm focus:outline-none"
          >
            <Send size={13} />
            Start Outreach ({influencers.length})
          </button>
        </DialogTrigger>
      )}

      <DialogContent className="sm:max-w-[540px] p-0 overflow-hidden bg-white dark:bg-[#0a0a0a] border-zinc-200 dark:border-white/10 shadow-2xl rounded-xl font-sans">
        {/* Header */}
        <div className="px-6 py-4 border-b border-zinc-200 dark:border-white/5 flex items-center justify-between">
          <div>
            <DialogTitle className="text-[15px] font-medium text-zinc-900 dark:text-[#ededed] flex items-center gap-2">
              <Sparkles size={16} className="text-emerald-500" />
              Configure Outreach Campaign
            </DialogTitle>
            <DialogDescription className="text-[13px] text-zinc-500 dark:text-[#a1a1aa] mt-0.5">
              Generating hyper-personalized pitches for {influencers.length}{" "}
              {influencers.length === 1 ? "creator" : "creators"}.
            </DialogDescription>
          </div>
        </div>

        <div className="px-6 py-4 space-y-5 max-h-[72vh] overflow-y-auto custom-scrollbar">
          {/* Target Creator Previews */}
          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold tracking-wider text-zinc-400 dark:text-zinc-500 uppercase">
              Selected Creators ({influencers.length})
            </span>
            <div className="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto p-1.5 bg-zinc-50 dark:bg-zinc-900/40 rounded-lg border border-zinc-200/70 dark:border-white/5">
              {influencers.slice(0, 8).map((creator) => (
                <div
                  key={creator.id}
                  className="flex items-center gap-1.5 px-2 py-0.5 bg-white dark:bg-zinc-800/80 rounded border border-zinc-200 dark:border-white/10 text-[11px] text-zinc-700 dark:text-zinc-300"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span className="font-medium truncate max-w-[120px]">{creator.title}</span>
                </div>
              ))}
              {influencers.length > 8 && (
                <div className="px-2 py-0.5 text-[11px] font-medium text-zinc-500">
                  +{influencers.length - 8} more
                </div>
              )}
            </div>
          </div>

          {/* Question 1: Collaboration Model */}
          <div className="space-y-2">
            <div>
              <span className="text-[11px] font-semibold tracking-wider text-zinc-400 dark:text-zinc-500 uppercase">
                1. Collaboration Model
              </span>
              <p className="text-[12px] text-zinc-500 dark:text-zinc-400">
                How should the pitch frame the commercial partnership?
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {COLLABORATION_OPTIONS.map((option) => {
                const isSelected = collaborationType === option.id;
                const Icon = option.icon;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setCollaborationType(option.id)}
                    className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-left transition-all ${
                      isSelected
                        ? "border-zinc-900 bg-zinc-50/80 dark:border-white dark:bg-white/5"
                        : "border-zinc-200 dark:border-zinc-800/80 hover:border-zinc-300 dark:hover:border-zinc-700 bg-transparent"
                    }`}
                  >
                    <div
                      className={`w-4 h-4 mt-0.5 rounded-full border flex items-center justify-center shrink-0 transition-colors ${
                        isSelected
                          ? "border-zinc-900 bg-zinc-900 dark:border-white dark:bg-white"
                          : "border-zinc-300 dark:border-zinc-600"
                      }`}
                    >
                      {isSelected && (
                        <div className="w-1.5 h-1.5 rounded-full bg-white dark:bg-black" />
                      )}
                    </div>
                    <div className="space-y-0.5 min-w-0">
                      <div className="flex items-center gap-1.5 text-[12px] font-medium text-zinc-900 dark:text-zinc-100">
                        <Icon size={12} className="opacity-70" />
                        <span>{option.label}</span>
                      </div>
                      <p className="text-[11px] text-zinc-500 leading-tight">
                        {option.desc}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Question 2: Deliverables & Requirements */}
          <div className="space-y-2">
            <div>
              <span className="text-[11px] font-semibold tracking-wider text-zinc-400 dark:text-zinc-500 uppercase">
                2. Deliverables & Expectations
              </span>
              <p className="text-[12px] text-zinc-500 dark:text-zinc-400">
                Select required deliverables to incorporate directly into personalized pitches.
              </p>
            </div>

            <div className="space-y-1.5">
              {DEFAULT_DELIVERABLES.map((deliv) => {
                const isChecked = selectedDeliverables.includes(deliv);
                return (
                  <button
                    key={deliv}
                    type="button"
                    onClick={() => toggleDeliverable(deliv)}
                    className="flex items-center gap-2.5 w-full text-left p-1.5 hover:bg-zinc-50 dark:hover:bg-white/5 rounded-md transition-colors"
                  >
                    <div
                      className={`w-[14px] h-[14px] rounded-[3px] border flex items-center justify-center shrink-0 transition-colors ${
                        isChecked
                          ? "border-zinc-900 bg-zinc-900 dark:border-white dark:bg-white"
                          : "border-zinc-300 dark:border-zinc-700 bg-transparent"
                      }`}
                    >
                      {isChecked && (
                        <Check size={10} className="text-white dark:text-black stroke-[3]" />
                      )}
                    </div>
                    <span
                      className={`text-[12px] transition-colors ${
                        isChecked
                          ? "text-zinc-900 dark:text-[#ededed] font-medium"
                          : "text-zinc-600 dark:text-zinc-400"
                      }`}
                    >
                      {deliv}
                    </span>
                  </button>
                );
              })}

              {/* Any custom deliverable added */}
              {selectedDeliverables
                .filter((d) => !DEFAULT_DELIVERABLES.includes(d))
                .map((custom) => (
                  <div
                    key={custom}
                    className="flex items-center justify-between p-1.5 bg-zinc-100 dark:bg-zinc-800/60 rounded-md text-[12px] text-zinc-800 dark:text-zinc-200"
                  >
                    <div className="flex items-center gap-2">
                      <Check size={12} className="text-emerald-500" />
                      <span>{custom}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleDeliverable(custom)}
                      className="text-zinc-400 hover:text-rose-500"
                    >
                      <X size={13} />
                    </button>
                  </div>
                ))}

              {/* Add custom item */}
              <div className="flex items-center gap-2 pt-1">
                <input
                  type="text"
                  placeholder="Add custom deliverable (e.g., 1x TikTok Reel)..."
                  value={customDeliverable}
                  onChange={(e) => setCustomDeliverable(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCustomDeliverable();
                    }
                  }}
                  className="flex-1 px-2.5 py-1 text-[12px] bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-md focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400"
                />
                <button
                  type="button"
                  onClick={addCustomDeliverable}
                  disabled={!customDeliverable.trim()}
                  className="px-2.5 py-1 text-[11px] font-medium border border-zinc-200 dark:border-zinc-800 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-40"
                >
                  <Plus size={13} className="inline mr-1" />
                  Add
                </button>
              </div>
            </div>
          </div>

          {error && (
            <div className="p-2.5 text-[12px] rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-500">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-zinc-50 dark:bg-[#0c0d0e] border-t border-zinc-200 dark:border-white/5 flex items-center justify-between">
          <span className="text-[11px] text-zinc-500 font-mono">
            Model: Gemini 3.8 Flash • Parallel Workers: 5
          </span>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              disabled={isSubmitting}
              className="px-3 py-1.5 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleStartOutreach}
              disabled={isSubmitting || influencers.length === 0}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium bg-zinc-900 dark:bg-white text-white dark:text-black rounded-md hover:bg-zinc-800 dark:hover:bg-zinc-100 transition-colors shadow-sm disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  Initializing Workflow...
                </>
              ) : (
                <>
                  <Send size={13} />
                  Generate Pitches ({influencers.length})
                </>
              )}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
