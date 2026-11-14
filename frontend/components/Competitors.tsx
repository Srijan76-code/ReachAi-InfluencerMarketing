"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Segmented } from "@/components/ui/segmented";
import { useCampaignStore } from "@/store/campaignStore";

const MAX = 10;

/** Competitors in the brief (roadmap F1.19): creators whose sponsored posts promote one get a badge, and the
 * campaign chooses whether that's a plus, a minus, or just shown. Empty = ReachAI suggests them. */
export default function Competitors() {
  const competitors = useCampaignStore((s) => s.competitors);
  const mode = useCampaignStore((s) => s.competitorMode);
  const setField = useCampaignStore((s) => s.setField);
  const [draft, setDraft] = useState("");

  const add = () => {
    const name = draft.trim().replace(/,$/, "").slice(0, 60);
    if (name.length >= 2 && !competitors.some((c) => c.toLowerCase() === name.toLowerCase()) && competitors.length < MAX) {
      setField("competitors", [...competitors, name]);
    }
    setDraft("");
  };

  return (
    <div className="space-y-2">
      <label htmlFor="competitor-input" className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">Competitors</label>
      <p className="text-[11px] text-zinc-500">Creators who promoted one recently get a badge. Leave empty and ReachAI finds them.</p>
      <div className="flex flex-wrap items-center gap-1.5 min-h-[34px] rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] px-2 py-1.5 focus-within:border-zinc-400 dark:focus-within:border-zinc-600">
        {competitors.map((c) => (
          <span key={c} className="inline-flex items-center gap-1 rounded-[4px] bg-zinc-100 dark:bg-zinc-800/70 px-1.5 py-0.5 text-xs text-zinc-800 dark:text-zinc-200">
            {c}
            <button type="button" aria-label={`Remove ${c}`} onClick={() => setField("competitors", competitors.filter((x) => x !== c))}
              className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"><X size={11} /></button>
          </span>
        ))}
        <input id="competitor-input" value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={add}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); }
            if (e.key === "Backspace" && !draft && competitors.length) setField("competitors", competitors.slice(0, -1));
          }}
          placeholder={competitors.length ? "" : "e.g. Notion, ClickUp"} disabled={competitors.length >= MAX}
          className="flex-1 min-w-[90px] bg-transparent text-xs text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none" />
      </div>
      <Segmented label="What a competitor promotion means" size="sm" value={mode}
        onChange={(v) => setField("competitorMode", v)}
        options={[{ value: "show", label: "Just show" }, { value: "prefer", label: "Prefer them" }, { value: "avoid", label: "Avoid them" }]} />
    </div>
  );
}
