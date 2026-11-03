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
      <div className="relative">
        <span className="pointer-events-none absolute inset-y-0 start-3 z-10 flex items-center text-sm text-muted-foreground">
          $
        </span>
        <Input
          className="rounded-md border-zinc-200 bg-zinc-50 ps-7 text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-100"
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
