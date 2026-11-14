import { TrendingUp, Flame, AlertTriangle, Globe, Clock, Swords } from "lucide-react";
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
  data_expired: {
    label: "Data expired",
    help: "YouTube's rules let us keep a channel's numbers for 30 days. Run the campaign again to get fresh numbers.",
    icon: Clock,
    className: "text-zinc-600 dark:text-zinc-400 bg-zinc-500/10 border-zinc-500/20",
  },
  competitor: {
    label: "Competitor",
    help: "Recently promoted one of your competitors in a sponsored post.",
    icon: Swords,
    className: "text-amber-700 dark:text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  country_unknown: {
    label: "Country unknown",
    help: "No country listed and its posts give no clear clue, so we can't confirm its audience is in your market. On YouTube and LinkedIn it's ranked a little lower.",
    icon: Globe,
    className: "text-zinc-600 dark:text-zinc-400 bg-zinc-500/10 border-zinc-500/20",
  },
};

export function knownFlags(flags: string[] | undefined | null): string[] {
  return (flags ?? []).filter((f) => f in BADGES);
}

/** `compact`: with many badges, show each as a small coloured icon (name and meaning on hover), so
 *  every badge stays visible on one line. "auto" turns compact on at 3 or more badges. */
export function CreatorBadges({ flags, size = "sm", compact = false, help = {} }: {
  flags?: string[] | null;
  size?: "sm" | "md";
  compact?: boolean | "auto";
  help?: Record<string, string | undefined>; // per-creator detail, e.g. which competitor
}) {
  const shown = knownFlags(flags);
  if (!shown.length) return null;
  const iconOnly = compact === "auto" ? shown.length >= 3 : compact;
  const text = size === "sm" ? "text-[9px]" : "text-[11px]";
  return (
    <span className={`inline-flex items-center gap-1 ${iconOnly ? "flex-nowrap" : "flex-wrap"}`}>
      {shown.map((f) => {
        const b = BADGES[f];
        const Icon = b.icon;
        return (
          <Tooltip key={f}>
            <TooltipTrigger asChild>
              <span
                aria-label={b.label}
                className={`inline-flex items-center gap-1 rounded-[4px] border font-semibold tracking-wide cursor-help whitespace-nowrap ${iconOnly ? "p-[3px]" : "px-1.5 py-0.5"} ${text} ${b.className}`}
              >
                <Icon size={size === "sm" ? (iconOnly ? 10 : 9) : 11} aria-hidden />
                {!iconOnly && b.label}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[220px] text-xs">
              {iconOnly && <span className="block font-semibold mb-0.5">{b.label}</span>}
              {help[f] ?? b.help}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </span>
  );
}

/** Flags to show for a result, including "data_expired" when the nightly refresh removed its numbers. */
export function badgeFlags(lead: { flags?: string[] | null; data_expired?: boolean }): string[] {
  return [...(lead.data_expired ? ["data_expired"] : []), ...(lead.flags ?? [])];
}

/** "Sponsored posts for Notion (2), ClickUp (1)" from a result's competitor_promos. */
export function competitorHelp(promos?: { brand: string; posts: number }[] | null): Record<string, string | undefined> {
  if (!promos?.length) return {};
  return { competitor: `Sponsored posts for ${promos.map((p) => `${p.brand} (${p.posts})`).join(", ")}.` };
}
