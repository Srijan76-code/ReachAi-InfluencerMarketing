import { CreatorAvatar } from "@/components/CreatorAvatar";
import type { Influencer } from "@/data/influencerList";
import { CreatorBadges, badgeFlags } from "@/components/CreatorBadges";
import { ShieldCheck, Info, Bookmark } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

// Same thresholds as the labels (backend app/judge/constants.py: STRONG_BUY_FROM, CONSIDER_FROM)
const STRONG_BUY_FROM = 60;
const CONSIDER_FROM = 45;

const STATUS_STYLES = {
  "Strong Buy": "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
  Consider: "text-amber-500 bg-amber-500/10 border-amber-500/20",
  Avoid: "text-rose-500 bg-rose-500/10 border-rose-500/20",
} as const;

const LABEL = "text-[9px] font-bold tracking-widest uppercase whitespace-nowrap flex items-center gap-1";

function Help({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info size={10} className="text-zinc-400/70 dark:text-zinc-600/70 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-help" />
      </TooltipTrigger>
      <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-800 dark:text-zinc-200 shadow-xl max-w-[220px]">
        {text}
      </TooltipContent>
    </Tooltip>
  );
}

export const InfluencerRow = ({
  influencer,
  rank,
  isSelected = false,
  isSaved = false,
  onToggleSave = () => {},
  readOnly = false,
}: {
  influencer: Influencer;
  rank: number;
  isSelected?: boolean;
  isSaved?: boolean;
  onToggleSelection?: (id: string) => void;
  onToggleSave?: (influencer: Influencer) => void;
  readOnly?: boolean; // shared view: no shortlist button
}) => {
  const { title, metrics, deal_status, final_score } = influencer;
  const expired = Boolean(influencer.data_expired); // numbers removed after 30 days (YouTube rules)
  const dash = "—";
  const score = Math.round(final_score ?? 0);
  const fit = Math.round(Number(influencer.score_breakdown?.strategy_score ?? 0));
  const ring = score >= STRONG_BUY_FROM ? "text-emerald-500" : score >= CONSIDER_FROM ? "text-amber-500" : "text-rose-500";

  return (
    <div className={`group flex items-center gap-5 px-4 py-3 hover:bg-zinc-100 dark:hover:bg-[#121314] transition-all cursor-pointer text-[13px] ${isSelected ? "bg-zinc-50 dark:bg-zinc-800/20" : "bg-white dark:bg-[#0c0d0e]"}`}>
      {/* rank */}
      <div className="w-7 flex justify-end pr-2 items-center flex-shrink-0 select-none">
        <span className={`text-[11px] font-medium font-mono tracking-wider ${
          rank === 1 ? "text-amber-500 dark:text-amber-400/90" :
          rank === 2 ? "text-slate-500 dark:text-slate-300/90" :
          rank === 3 ? "text-amber-700 dark:text-amber-600/80" :
          "text-zinc-400 dark:text-zinc-600"
        }`}>
          {String(rank).padStart(2, "0")}
        </span>
      </div>

      {/* identity: flexes and truncates, so a long name never runs into the next column */}
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <CreatorAvatar
          name={title}
          src={influencer.avatar_url}
          className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 shadow-sm"
          textClassName="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]"
        />
        <div className="flex flex-col gap-1 leading-none min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-semibold text-sm text-zinc-800 dark:text-zinc-200 truncate group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors" title={title}>
              {title}
            </span>
            {influencer.country ? (
              <span
                className={`text-zinc-600 dark:text-zinc-400 font-bold text-[10px] tracking-widest flex-shrink-0 ${influencer.country_source === "jev" ? "underline decoration-dotted underline-offset-2 cursor-help" : ""}`}
                title={influencer.country_source === "jev" ? "Judged by Jev from their posts: YouTube doesn't list a country for this channel" : undefined}
              >
                {influencer.country}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-1 min-w-0">
            <span className={`flex-shrink-0 px-1.5 py-0.5 rounded-[4px] border text-[9px] font-bold tracking-wider whitespace-nowrap ${STATUS_STYLES[deal_status] ?? STATUS_STYLES.Consider}`}>
              {deal_status}
            </span>
            <CreatorBadges flags={badgeFlags(influencer)} compact="auto" />
          </div>
        </div>
      </div>

      {/* verdict */}
      <div className="hidden sm:flex items-center gap-8 px-6 border-x border-zinc-200/60 dark:border-zinc-800/60 flex-shrink-0">
        <div className="flex flex-col items-center min-w-[40px]">
          <span className={`${LABEL} text-zinc-600 dark:text-zinc-400 mb-1`}>
            Fit <Help text="How well their content and audience match your brief." />
          </span>
          <span className="font-mono font-bold text-blue-400 text-[13px]">{fit}%</span>
        </div>
        <div className="flex flex-col items-center min-w-[40px]">
          <span className={`${LABEL} text-zinc-600 dark:text-zinc-400 mb-1`}>
            Health <Help text="Steady views, real engagement and regular posting." />
          </span>
          <div className="flex items-center gap-1">
            <ShieldCheck size={12} className={influencer.score_breakdown.health_score > 80 ? "text-emerald-500" : "text-zinc-600 dark:text-zinc-400"} />
            <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200 text-[13px]">{influencer.score_breakdown.health_score}%</span>
          </div>
        </div>
      </div>

      {/* numbers */}
      <div className="flex items-center gap-8 flex-shrink-0">
        <div className="hidden md:flex flex-col items-end justify-center min-w-[90px] gap-1">
          <span className="font-mono text-[12px] font-bold text-zinc-600 dark:text-zinc-400 flex items-center gap-1.5 justify-end whitespace-nowrap">
            {expired ? dash : `${(metrics.avg_views / 1000).toFixed(1)}k`}
            <span className="text-[9px] font-bold tracking-wide flex items-center gap-1">
              Views <Help text="Typical views on their recent videos: how many people will see your product." />
            </span>
          </span>
          <span className="font-mono text-[12px] font-bold text-zinc-600 dark:text-zinc-400 flex items-center gap-1.5 justify-end whitespace-nowrap">
            {expired ? dash : `${metrics.engagement_rate}%`}
            <span className="text-[9px] font-bold tracking-wide flex items-center gap-1">
              Eng. <Help text="Likes and comments per view. Higher means the audience listens to this creator." />
            </span>
          </span>
        </div>

        <div className="hidden lg:flex flex-col justify-center min-w-[72px]">
          <span className={`${LABEL} mb-1`}>
            Price <Help text="Fair price for one sponsored video." />
          </span>
          <span className="font-mono text-[12px] font-bold text-rose-400 leading-none">
            {expired || influencer.valuation == null ? dash : `$${Math.round(influencer.valuation)}`}
          </span>
        </div>

        <div className="hidden xl:flex flex-col justify-center min-w-[64px]">
          <span className={`${LABEL} mb-1`}>
            Clicks <Help text="Estimated people who will click your link per video." />
          </span>
          <span className="font-mono text-[12px] font-bold text-emerald-400 leading-none">
            {expired ? dash : `~${String(metrics.forecast || "").split(" ")[0].replace("~", "")}`}
          </span>
        </div>

        <div className="flex flex-col items-center justify-center min-w-[50px] pl-6 border-l border-zinc-200/60 dark:border-zinc-800/60">
          <span className={`${LABEL} mb-1`}>
            Impact <Help text="The overall score (0-100): fit, channel health and risk combined." />
          </span>
          <div className="relative w-9 h-9 flex items-center justify-center" aria-label={`Impact ${score} of 100`}>
            <svg className="w-9 h-9 -rotate-90" viewBox="0 0 36 36">
              <circle className="text-zinc-200 dark:text-zinc-800" strokeWidth="2.5" stroke="currentColor" fill="transparent" r="15" cx="18" cy="18" />
              <circle className={ring} strokeWidth="2.5" strokeDasharray="100" strokeDashoffset={100 - score}
                strokeLinecap="round" stroke="currentColor" fill="transparent" r="15" cx="18" cy="18" pathLength="100" />
            </svg>
            <span className="absolute text-[11px] font-mono font-bold text-zinc-800 dark:text-zinc-200">{score}</span>
          </div>
        </div>
      </div>

      {/* shortlist */}
      <div className="w-7 flex justify-center items-center flex-shrink-0">
        {!readOnly && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleSave(influencer);
            }}
            title={isSaved ? "Remove from shortlist" : "Add to shortlist"}
            aria-label={isSaved ? "Remove from shortlist" : "Add to shortlist"}
            aria-pressed={isSaved}
            className="p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-all text-zinc-400 hover:text-amber-500"
          >
            <Bookmark size={15} className={isSaved ? "fill-amber-500 text-amber-500" : "text-zinc-400"} />
          </button>
        )}
      </div>
    </div>
  );
};
