"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Send, Layers, Gift, Link2, Video, Loader2, Info, Check, Plus, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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
    desc: "60–90s dedicated integration in a standard upload.",
    tooltip: "The AI will pitch a paid mid-roll or pre-roll placement inside the creator's existing video format.",
    icon: Video,
  },
  {
    id: "dedicated_review",
    label: "Dedicated Review",
    desc: "Full video dedicated to your product.",
    tooltip: "The entire video revolves around reviewing your product — higher commitment but stronger social proof.",
    icon: Layers,
  },
  {
    id: "affiliate",
    label: "Affiliate & Performance",
    desc: "Commission-based with tracking link.",
    tooltip: "No upfront fee — the creator earns a cut per sale via a unique discount code or referral link.",
    icon: Link2,
  },
  {
    id: "gifting",
    label: "Product Gifting / Seeding",
    desc: "Free product in exchange for an honest review.",
    tooltip: "You send the product at no charge; the creator posts an organic review. Low cost, lower control.",
    icon: Gift,
  },
];

const DEFAULT_DELIVERABLES = [
  "1x 60s Mid-roll Integration",
  "Pinned Comment & Top Description Link",
  "30-day Organic & Paid Usage Rights",
  "Cross-post to Instagram Story or X",
];

// ─── Shared primitives ──────────────────────────────────────────────────────

const CollabRadio = ({
  option,
  selected,
  onSelect,
}: {
  option: (typeof COLLABORATION_OPTIONS)[number];
  selected: boolean;
  onSelect: () => void;
}) => {
  const Icon = option.icon;
  return (
    <button
      onClick={onSelect}
      className={`flex items-start gap-2.5 w-full p-1.5 hover:bg-zinc-50 dark:hover:bg-white/5 rounded-md transition-colors text-left group focus:outline-none`}
    >
      <div
        className={`w-[14px] h-[14px] mt-[3px] rounded-full border flex items-center justify-center shrink-0 transition-colors ${
          selected
            ? "border-zinc-900 bg-zinc-900 dark:border-white dark:bg-white"
            : "border-zinc-300 dark:border-zinc-700 group-hover:border-zinc-400 dark:group-hover:border-zinc-500"
        }`}
      >
        {selected && <div className="w-[6px] h-[6px] rounded-full bg-white dark:bg-black" />}
      </div>
      <div className="flex flex-col gap-0.5 min-w-0">
        <div className="flex items-center gap-1.5">
          <Icon size={11} className="opacity-50 shrink-0" />
          <span
            className={`text-[13px] font-medium transition-colors ${
              selected
                ? "text-zinc-900 dark:text-[#ededed]"
                : "text-zinc-600 dark:text-[#a1a1aa] group-hover:text-zinc-900 dark:group-hover:text-[#ededed]"
            }`}
          >
            {option.label}
          </span>
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info size={11} className="text-zinc-400 dark:text-zinc-600 hover:text-zinc-600 dark:hover:text-zinc-400 transition-colors cursor-default shrink-0" />
              </TooltipTrigger>
              <TooltipContent side="right" className="max-w-[220px] text-[11px]">
                {option.tooltip}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <span className="text-[11px] text-zinc-500 dark:text-zinc-600 leading-tight">{option.desc}</span>
      </div>
    </button>
  );
};

const DeliverableCheckbox = ({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) => (
  <button
    onClick={onChange}
    className="flex items-center gap-2.5 w-full text-left p-1.5 hover:bg-zinc-50 dark:hover:bg-white/5 rounded-md transition-colors group focus:outline-none py-1"
  >
    <div
      className={`w-[14px] h-[14px] rounded-[3px] border flex items-center justify-center shrink-0 transition-colors ${
        checked
          ? "border-zinc-900 bg-zinc-900 dark:border-white dark:bg-white"
          : "border-zinc-300 dark:border-zinc-700 group-hover:border-zinc-400 dark:group-hover:border-zinc-500"
      }`}
    >
      {checked && (
        <svg width="9" height="7" viewBox="0 0 9 7" fill="none" className="text-white dark:text-black">
          <path d="M1 3.5L3.5 6L8 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
    <span
      className={`text-[13px] transition-colors ${
        checked
          ? "text-zinc-900 dark:text-[#ededed]"
          : "text-zinc-500 dark:text-[#a1a1aa] group-hover:text-zinc-700 dark:group-hover:text-zinc-300"
      }`}
    >
      {label}
    </span>
  </button>
);

// ─── Main Component ──────────────────────────────────────────────────────────

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

    const creatorIds = influencers
      .map((inf) => inf.id || (inf as any).creator_id)
      .filter(Boolean);

    try {
      const res = await api(`/api/outreach/campaigns/${campaignId}/jobs`, {
        method: "POST",
        data: {
          selected_creator_ids: creatorIds,
          collaboration_type: collaborationType,
          deliverables: selectedDeliverables,
          auto_start: true,
        },
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

  const customDeliverables = selectedDeliverables.filter((d) => !DEFAULT_DELIVERABLES.includes(d));

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

      <DialogContent className="sm:max-w-[480px] p-0 overflow-hidden bg-white dark:bg-[#0a0a0a] border-zinc-200 dark:border-white/10 shadow-2xl rounded-xl font-sans">

        {/* Header */}
        <div className="px-5 py-4 border-b border-zinc-200 dark:border-white/5">
          <DialogTitle className="text-[15px] font-medium text-zinc-900 dark:text-[#ededed]">
            Start Outreach
          </DialogTitle>
          <DialogDescription className="text-[13px] text-zinc-500 dark:text-[#a1a1aa] mt-1">
            Configure pitches for {influencers.length} {influencers.length === 1 ? "creator" : "creators"}.
          </DialogDescription>
        </div>

        <div className="p-5 space-y-6">

          {/* Creators */}
          <div className="space-y-2">
            <label className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">
              Selected creators
            </label>
            <div className="flex flex-wrap gap-1.5">
              {influencers.slice(0, 6).map((creator) => (
                <div
                  key={creator.id}
                  className="flex items-center gap-1.5 px-2 py-0.5 bg-zinc-100 dark:bg-white/[0.06] rounded border border-zinc-200 dark:border-white/8 text-[11px] text-zinc-600 dark:text-zinc-400"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                  <span className="truncate max-w-[110px]">{creator.title}</span>
                </div>
              ))}
              {influencers.length > 6 && (
                <div className="px-2 py-0.5 text-[11px] text-zinc-400 dark:text-zinc-600">
                  +{influencers.length - 6} more
                </div>
              )}
            </div>
          </div>

          {/* Collaboration model */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <label className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">
                Collaboration model
              </label>
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info size={11} className="text-zinc-400 dark:text-zinc-600 cursor-default" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[220px] text-[11px]">
                    This frames how the AI writes each pitch — the commercial structure changes the tone and ask.
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <div className="flex flex-col gap-0.5 -ml-1.5">
              {COLLABORATION_OPTIONS.map((opt) => (
                <CollabRadio
                  key={opt.id}
                  option={opt}
                  selected={collaborationType === opt.id}
                  onSelect={() => setCollaborationType(opt.id)}
                />
              ))}
            </div>
          </div>

          {/* Deliverables */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <label className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">
                Deliverables
              </label>
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info size={11} className="text-zinc-400 dark:text-zinc-600 cursor-default" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[240px] text-[11px]">
                    Checked items are woven directly into each AI-generated pitch so the creator knows exactly what's expected.
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <div className="flex flex-col -ml-1.5">
              {DEFAULT_DELIVERABLES.map((deliv) => (
                <DeliverableCheckbox
                  key={deliv}
                  label={deliv}
                  checked={selectedDeliverables.includes(deliv)}
                  onChange={() => toggleDeliverable(deliv)}
                />
              ))}

              {/* Custom deliverables added by the user */}
              {customDeliverables.map((custom) => (
                <div
                  key={custom}
                  className="flex items-center justify-between px-1.5 py-1 rounded-md text-[13px] text-zinc-700 dark:text-zinc-300"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-[14px] h-[14px] rounded-[3px] border border-zinc-900 bg-zinc-900 dark:border-white dark:bg-white flex items-center justify-center shrink-0">
                      <svg width="9" height="7" viewBox="0 0 9 7" fill="none" className="text-white dark:text-black">
                        <path d="M1 3.5L3.5 6L8 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                    <span>{custom}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleDeliverable(custom)}
                    className="text-zinc-400 hover:text-rose-500 transition-colors focus:outline-none"
                  >
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>

            {/* Add custom */}
            <div className="flex items-center gap-2 pt-0.5">
              <input
                type="text"
                placeholder="Add custom deliverable..."
                value={customDeliverable}
                onChange={(e) => setCustomDeliverable(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCustomDeliverable();
                  }
                }}
                className="flex-1 px-2.5 py-1.5 text-[12px] bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-md focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-600"
              />
              <button
                type="button"
                onClick={addCustomDeliverable}
                disabled={!customDeliverable.trim()}
                className="px-2.5 py-1.5 text-[11px] font-medium border border-zinc-200 dark:border-zinc-800 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-40 flex items-center gap-1 focus:outline-none"
              >
                <Plus size={12} />
                Add
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="p-2.5 text-[12px] rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-500">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-zinc-200 dark:border-white/5 bg-zinc-50/50 dark:bg-[#0a0a0a] flex items-center justify-between">
          <button
            type="button"
            onClick={() => setOpen(false)}
            disabled={isSubmitting}
            className="px-4 py-2 text-[13px] font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white transition-colors focus:outline-none"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleStartOutreach}
            disabled={isSubmitting || influencers.length === 0}
            className="px-4 py-2 text-[13px] font-medium bg-zinc-900 hover:bg-zinc-800 dark:bg-[#ededed] dark:hover:bg-white disabled:opacity-50 text-white dark:text-black rounded-md transition-all shadow-sm focus:outline-none flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                Starting...
              </>
            ) : (
              <>
                Generate pitches
                <Send size={13} className="opacity-70" />
              </>
            )}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
