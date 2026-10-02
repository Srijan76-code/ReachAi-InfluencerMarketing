"use client";

import { useId } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { RiInstagramFill, RiYoutubeFill } from "@remixicon/react";
import { useCampaignStore } from "@/store/campaignStore";

export default function MultiPlatform() {
  const id = useId();
  const platforms = useCampaignStore((state) => state.platforms);
  const setField = useCampaignStore((state) => state.setField);

  const items = [
    { Icon: RiYoutubeFill, label: "YouTube", value: "1", disabled: false },
    { Icon: RiInstagramFill, label: "Instagram", value: "2", disabled: true },
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
        Platforms <span className="text-rose-500">*</span>
      </label>
      <div className="flex gap-2 flex-wrap">
        {items.map((item) => (
          <div
            key={`${id}-${item.value}`}
            className="relative flex items-center justify-between gap-3 rounded-md border border-input p-2.5 shadow-xs cursor-pointer has-data-[state=checked]:border-primary/50"
          >
            <div className="flex items-center gap-2">
              <item.Icon aria-hidden="true" className="opacity-60" size={15} />
              <label
                htmlFor={`${id}-${item.value}`}
                className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300 cursor-pointer"
              >
                {item.label}
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
