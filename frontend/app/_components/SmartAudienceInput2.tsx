"use client";

import { CirclePlus, Info } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { INDUSTRY_ONTOLOGY } from "@/data/INDUSTRY_ONTOLOGY";
import { useCampaignStore } from "@/store/campaignStore";

export function SmartAudienceInput2() {
  const targetAudience = useCampaignStore((state) => state.targetAudience);
  const setField = useCampaignStore((state) => state.setField);

  const chips: string[] = INDUSTRY_ONTOLOGY.edtech.chips_persona;

  const handleChipClick = (chipText: string) => {
    setField("targetAudience", targetAudience ? `${targetAudience} ${chipText}` : chipText);
  };

  return (
    <div className="space-y-2">
      <label className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">
        Target Audience <span className="text-rose-500">*</span>
      </label>
      <Textarea
        id="targetAudience"
        value={targetAudience}
        onChange={(e) => setField("targetAudience", e.target.value)}
        placeholder="e.g. Final-year college students looking for internships"
        className="text-[13px] min-h-[80px] resize-none"
      />
      <div className="flex items-center gap-1 text-zinc-400">
        <Info size={11} />
        <p className="text-[11px]">Who is your ideal customer?</p>
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
