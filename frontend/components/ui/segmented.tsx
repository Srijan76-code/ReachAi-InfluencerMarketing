"use client";

import { useId } from "react";
import { motion } from "motion/react";

export type SegmentOption<T extends string> = { value: T; label: React.ReactNode; count?: number; disabled?: boolean };

/**
 * The app's switch (All | Shortlist, post tabs, share scope…): the selected highlight slides to the new
 * option instead of jumping. `size="md"` matches the 30px toolbar buttons; "sm" fits inside panels.
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  size = "md",
}: {
  options: SegmentOption<T>[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  const id = useId();
  const box = size === "md" ? "h-[30px] p-[3px] text-xs" : "h-7 p-0.5 text-[11px]";
  return (
    <div role="tablist" aria-label={label} className={`relative flex items-center gap-0.5 w-fit rounded-md border border-zinc-200 dark:border-zinc-800 ${box}`}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            type="button"
            aria-selected={on}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            className={`relative h-full px-2.5 rounded-[4px] font-medium whitespace-nowrap transition-colors disabled:opacity-40 ${on ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"}`}
          >
            {on && (
              <motion.span
                layoutId={`seg-${id}`}
                className="absolute inset-0 rounded-[4px] bg-zinc-100 dark:bg-zinc-800 shadow-[0_1px_0_rgba(0,0,0,0.04)]"
                aria-hidden
              />
            )}
            <span className="relative">
              {o.label}
              {o.count !== undefined && <span className="ml-1 font-mono opacity-60">{o.count}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
