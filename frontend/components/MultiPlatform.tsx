"use client";

import { useId } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { RiInstagramFill, RiLinkedinBoxFill, RiTwitterXFill, RiYoutubeFill } from "@remixicon/react";
import { useCampaignStore } from "@/store/campaignStore";
import { plural, useCredits } from "@/lib/credits";

export default function MultiPlatform() {
  const id = useId();
  const platforms = useCampaignStore((state) => state.platforms);
  const setField = useCampaignStore((state) => state.setField);

  // Live platforms and their cost come from the backend (the same list billing charges for).
  const live = useCredits()?.search_credits ?? { youtube: 1 };
  const items = [
    { Icon: RiYoutubeFill, label: "YouTube", value: "youtube" },
    { Icon: RiTwitterXFill, label: "X", value: "x" },
    { Icon: RiInstagramFill, label: "Instagram", value: "instagram" },
    { Icon: RiLinkedinBoxFill, label: "LinkedIn", value: "linkedin" },
  ].map((i) => ({ ...i, disabled: !(i.value in live), credits: live[i.value] }));
  const soon = items.filter((i) => i.disabled).map((i) => i.label);

  const handleCheckedChange = (value: string, checked: boolean) => {
    if (checked) {
      setField("platforms", [...platforms, value]);
    } else {
      setField("platforms", platforms.filter((p) => p !== value));
    }
  };

  return (
    <div className="space-y-2">
      <label className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">
        Platforms
      </label>
      <p className="text-[11px] text-zinc-500">
        Leave all unticked and ReachAI picks the platforms that fit your product.
        {soon.length ? ` ${soon.join(", ")} coming soon.` : ""}
      </p>
      <div className="flex gap-2 flex-wrap">
        {items.map((item) => (
          <div
            key={`${id}-${item.value}`}
            className="relative flex items-center justify-between gap-3 rounded-md border border-zinc-200 bg-zinc-50 p-2.5 shadow-xs cursor-pointer has-data-[state=checked]:border-primary/50 dark:border-zinc-700 dark:bg-zinc-900/50"
          >
            <div className="flex items-center gap-2">
              <item.Icon aria-hidden="true" className="opacity-60" size={15} />
              <label
                htmlFor={`${id}-${item.value}`}
                className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300 cursor-pointer"
              >
                {item.label}
                {item.disabled ? (
                  <span className="ml-1 text-[10px] text-zinc-400">soon</span>
                ) : (
                  <span className="ml-1 text-[10px] text-zinc-400">{plural(item.credits ?? 1)}</span>
                )}
              </label>
            </div>
            <Checkbox
              className="order-1 after:absolute after:inset-0 h-3.5 w-3.5"
              checked={platforms.includes(item.value)}
              onCheckedChange={(checked) => handleCheckedChange(item.value, checked as boolean)}
              id={`${id}-${item.value}`}
              value={item.value}
              disabled={item.disabled}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
