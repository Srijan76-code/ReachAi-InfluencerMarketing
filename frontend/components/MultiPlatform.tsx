"use client";

import { useId } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { RiInstagramFill, RiLinkedinBoxFill, RiTwitterXFill, RiYoutubeFill } from "@remixicon/react";
import { useCampaignStore } from "@/store/campaignStore";

export default function MultiPlatform() {
  const id = useId();
  const platforms = useCampaignStore((state) => state.platforms);
  const setField = useCampaignStore((state) => state.setField);

  // Values are the platform names the backend understands. Platforms not built yet are shown but disabled.
  const items = [
    { Icon: RiYoutubeFill, label: "YouTube", value: "youtube", disabled: false },
    { Icon: RiInstagramFill, label: "Instagram", value: "instagram", disabled: true },
    { Icon: RiTwitterXFill, label: "X", value: "x", disabled: true },
    { Icon: RiLinkedinBoxFill, label: "LinkedIn", value: "linkedin", disabled: true },
  ];

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
        Leave all unticked and ReachAI picks the platforms that fit your product. Instagram, X and LinkedIn are coming soon.
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
                {item.disabled && <span className="ml-1 text-[10px] text-zinc-400">soon</span>}
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
