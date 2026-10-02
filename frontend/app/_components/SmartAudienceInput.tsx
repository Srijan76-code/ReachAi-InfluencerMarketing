"use client";

import { CirclePlus, Info } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { INDUSTRY_ONTOLOGY } from "@/data/INDUSTRY_ONTOLOGY";
import { useCampaignStore } from "@/store/campaignStore";

export function SmartAudienceInput() {
  const pitch = useCampaignStore((state) => state.pitch);
  const setField = useCampaignStore((state) => state.setField);

  const chips = ["Coding Bootcamp", "Placement Prep", "University Course", "Upskilling"];

  const handleChipClick = (chipText: string) => {
    setField("pitch", pitch ? `${pitch} ${chipText}` : chipText);
  };

  return (
    <div className="space-y-2">
      <label className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">
        What are you selling? <span className="text-rose-500">*</span>
      </label>
      <Textarea
        id="pitch"
        value={pitch}
        onChange={(e) => setField("pitch", e.target.value)}
        placeholder="e.g. A comprehensive Python bootcamp that helps students get hired at top tech companies..."
        className="text-[13px] min-h-[80px] resize-none"
      />
      <div className="flex items-center gap-1 text-zinc-400">
        <Info size={11} />
        <p className="text-[11px]">Describe your product and its main benefit in one sentence.</p>
      </div>
      <div className="flex flex-wrap gap-1.5 pt-1">
        {chips.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => handleChipClick(chip)}
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-zinc-600 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-md hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
          >
            <CirclePlus size={11} />
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
