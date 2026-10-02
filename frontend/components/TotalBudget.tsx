"use client";

import { useId } from "react";

import { Input } from "@/components/ui/input";

import { useCampaignStore } from "@/store/campaignStore";

export default function TotalBudget() {
  const id = useId();
  const totalBudget = useCampaignStore((state) => state.totalBudget);
  const setField = useCampaignStore((state) => state.setField);

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">Total campaign budget</label>
      <div className="flex rounded-md shadow-xs">
        <span className="-z-10 inline-flex items-center rounded-s-md border border-input bg-background px-3 text-muted-foreground text-sm">
          $
        </span>
        <Input
          className="-ms-px rounded-s-none shadow-none"
          id={id}
          placeholder="500"
          type="text"
          value={totalBudget}
          onChange={(e) => setField("totalBudget", e.target.value)}
        />
      </div>
    </div>
  );
}
