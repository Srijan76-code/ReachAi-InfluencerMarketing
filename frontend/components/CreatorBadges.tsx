import { TrendingUp, Flame, AlertTriangle, Globe } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Labels the discovery engine attaches to a creator (`flags` on each result). */
export const BADGES: Record<string, { label: string; help: string; icon: typeof TrendingUp; className: string }> = {
  rising: {
    label: "Rising",
    help: "Recent videos are doing much better than this creator's usual. Often cheaper now than they will be later.",
    icon: TrendingUp,
    className: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  trend: {
    label: "On trend",
    help: "Posts about what this niche is talking about right now.",
    icon: Flame,
    className: "text-orange-600 dark:text-orange-400 bg-orange-500/10 border-orange-500/20",
  },
  suspicious: {
    label: "Check engagement",
    help: "Views, likes or comments look unusual for a channel this size. Ask for audience stats before paying.",
    icon: AlertTriangle,
    className: "text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
  country_unknown: {
    label: "Country unknown",
    help: "This channel doesn't list a country, so we can't confirm its audience is in your market. It's ranked a little lower.",
    icon: Globe,
    className: "text-zinc-600 dark:text-zinc-400 bg-zinc-500/10 border-zinc-500/20",
  },
};

export function knownFlags(flags: string[] | undefined | null): string[] {
  return (flags ?? []).filter((f) => f in BADGES);
}

export function CreatorBadges({ flags, size = "sm" }: { flags?: string[] | null; size?: "sm" | "md" }) {
  const shown = knownFlags(flags);
  if (!shown.length) return null;
  const text = size === "sm" ? "text-[9px]" : "text-[11px]";
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {shown.map((f) => {
        const b = BADGES[f];
        const Icon = b.icon;
        return (
          <Tooltip key={f}>
            <TooltipTrigger asChild>
              <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[4px] border font-semibold tracking-wide cursor-help ${text} ${b.className}`}>
                <Icon size={size === "sm" ? 9 : 11} aria-hidden />
                {b.label}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[220px] text-xs">{b.help}</TooltipContent>
          </Tooltip>
        );
      })}
    </span>
  );
}
