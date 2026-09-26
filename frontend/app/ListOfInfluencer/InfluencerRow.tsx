import type { Influencer } from "@/data/influencerList";
import {
  ShieldCheck,
  MousePointerClick,
  MoreHorizontal,
  User,
  Info,
  Bookmark,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export const InfluencerRow = ({
  influencer,
  rank,
  isSelected = false,
  isSaved = false,
  onToggleSelection = () => {},
  onToggleSave = () => {},
}: {
  influencer: Influencer;
  rank: number;
  isSelected?: boolean;
  isSaved?: boolean;
  onToggleSelection?: (id: string) => void;
  onToggleSave?: (influencer: Influencer) => void;
}) => {
  const { title, subscribers, metrics, deal_status, final_score } = influencer;

  const statusStyles = {
    "Strong Buy": "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
    Consider: "text-amber-500 bg-amber-500/10 border-amber-500/20",
    Avoid: "text-rose-500 bg-rose-500/10 border-rose-500/20",
  };

  return (
    // Removed border-b and added internal bg to match the Linear "Backlog" card look
    <div className={`group flex items-center gap-5 px-4 py-3 hover:bg-zinc-100 dark:hover:bg-[#121314] transition-all cursor-pointer text-[13px] ${isSelected ? "bg-zinc-50 dark:bg-zinc-800/20" : "bg-white dark:bg-[#0c0d0e]"}`}>
      
      {/* --- ZONE -1: SELECTION (Migrated to Parent) --- */}
      {/* --- ZONE 0: RANK --- */}
      <div className="w-7 flex justify-end pr-2 items-center flex-shrink-0 select-none">
        <span className={`text-[11px] font-medium font-mono tracking-wider ${
          rank === 1 ? "text-amber-500 dark:text-amber-400/90" : 
          rank === 2 ? "text-slate-500 dark:text-slate-300/90" : 
          rank === 3 ? "text-amber-700 dark:text-amber-600/80" : 
          "text-zinc-400 dark:text-zinc-600"
        }`}>
          {String(rank).padStart(2, '0')}
        </span>
      </div>

      {/* --- ZONE 1: IDENTITY --- */}
      <div className="flex items-center gap-3 min-w-[240px] flex-1">
        <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 shadow-sm">
          <span className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">
            {title.charAt(0).toUpperCase()}
          </span>
        </div>

        <div className="flex flex-col gap-1 leading-none">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-zinc-800 dark:text-zinc-200 truncate group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors">
              {title}
            </span>
            <span className="text-zinc-600 dark:text-zinc-400 font-bold  text-[10px] tracking-widest flex-shrink-0">
              {influencer.country}
            </span>
          </div>
          <div className="leading-none">
            <span
              className={`px-1.5 py-0.5 rounded-[4px] border text-[9px] font-bold tracking-wider  ${statusStyles[deal_status]}`}
            >
              {deal_status}
            </span>
          </div>
        </div>
      </div>

      {/* --- ZONE 2: AI VERDICT --- */}
      <div className="hidden sm:flex items-center gap-10 px-8 border-x border-zinc-200/60 dark:border-zinc-800/60">
        <div className="flex flex-col items-center min-w-[40px]">
          <span className="text-[10px] font-bold text-zinc-600 dark:text-zinc-400  tracking-widest mb-1">
            Brand Fit
          </span>
          <div className="flex items-center gap-1">
            <span className="font-mono font-bold text-blue-400 text-[13px]">
              {influencer.score_breakdown.strategy_score}%
            </span>
          </div>
        </div>

        <div className="flex flex-col items-center min-w-[40px]">
          <span className="text-[10px] font-bold text-zinc-600 dark:text-zinc-400  tracking-widest mb-1">
            Health
          </span>
          <div className="flex items-center gap-1">
            <ShieldCheck
              size={12}
              className={
                influencer.score_breakdown.health_score > 80
                  ? "text-emerald-500"
                  : "text-zinc-600 dark:text-zinc-400"
              }
            />
            <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200 text-[13px]">
              {influencer.score_breakdown.health_score}%
            </span>
          </div>
        </div>
      </div>

      {/* --- ZONE 3: DATA GRID --- */}
      <div className="flex items-center gap-10 ml-auto ">
        {/* Block 1: Audience & Reach */}
        <div className="hidden md:flex flex-col items-end justify-center min-w-[90px] gap-1">
          <span className="font-mono text-[12px] font-bold text-zinc-600 dark:text-zinc-400 flex items-center gap-1.5 justify-end">
            {(metrics.avg_views / 1000).toFixed(1)}k
            <span className="text-[9px] font-bold text-zinc-600 dark:text-zinc-400 tracking-wide  flex items-center gap-1">
              Views
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info
                    size={10}
                    className="text-zinc-400/70 dark:text-zinc-600/70 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-help"
                  />
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-800 dark:text-zinc-200 shadow-xl"
                >
                  Tells you how many people will actually see your product.
                </TooltipContent>
              </Tooltip>
            </span>
          </span>
          <span className="font-mono text-[12px] font-bold text-zinc-600 dark:text-zinc-400 flex items-center gap-1.5 justify-end">
            {metrics.engagement_rate}%
            <span className="text-[9px] font-bold text-zinc-600 dark:text-zinc-400 tracking-wide  flex items-center gap-1">
              Eng.
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info
                    size={10}
                    className="text-zinc-400/70 dark:text-zinc-600/70 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-help"
                  />
                </TooltipTrigger>
                <TooltipContent
                  side="top"
                  className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-800 dark:text-zinc-200 shadow-xl"
                >
                  Tells you if the audience cares. Higher numbers mean they are
                  highly likely to listen to the creator.
                </TooltipContent>
              </Tooltip>
            </span>
          </span>
        </div>

        {/* Block 2: Fair Value */}
        <div className="hidden lg:flex flex-col  justify-center min-w-[80px]">
          <span className="text-[9px] font-bold  tracking-widest uppercase flex items-center gap-1 mb-1">
            Est. price
            <Tooltip>
              <TooltipTrigger asChild>
                <Info
                  size={10}
                  className="text-zinc-400/70 dark:text-zinc-600/70 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-help"
                />
              </TooltipTrigger>
              <TooltipContent
                side="top"
                className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-800 dark:text-zinc-200 shadow-xl"
              >
                The exact budget you need to set aside to sponsor 1 video.
              </TooltipContent>
            </Tooltip>
          </span>
          <span className="font-mono text-[12px] font-bold text-rose-400 leading-none">
            ${influencer.valuation}
          </span>
        </div>

        {/* Block 3: Yield */}
        <div className="hidden xl:flex flex-col  justify-center min-w-[80px] border-r border-zinc-200/60 dark:border-zinc-800/60 ">
          <span className="text-[9px] font-bold tracking-widest uppercase flex items-center gap-1 mb-1">
            Clicks
            <Tooltip>
              <TooltipTrigger asChild>
                <Info
                  size={10}
                  className="text-zinc-400/70 dark:text-zinc-600/70 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-help"
                />
              </TooltipTrigger>
              <TooltipContent
                side="top"
                className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-800 dark:text-zinc-200 shadow-xl"
              >
                The estimated number of people who will click your link to buy
                or sign up.
              </TooltipContent>
            </Tooltip>
          </span>
          <span className="font-mono text-[12px] font-bold text-emerald-400 leading-none">
            ~{metrics.forecast.split(" ")[0].replace("~", "")}
          </span>
        </div>

        {/* Block 4: Match Score */}
        <div className="flex flex-col items-center justify-center min-w-[50px]">
          <span className="text-[9px] font-bold tracking-widest uppercase flex items-center gap-1 mb-1.5">
            IMPACT
            <Tooltip>
              <TooltipTrigger asChild>
                <Info
                  size={10}
                  className="text-zinc-400/70 dark:text-zinc-600/70 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-help"
                />
              </TooltipTrigger>
              <TooltipContent
                side="top"
                className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-800 dark:text-zinc-200 shadow-xl"
              >
                Tells you how much this creator will move the needle for your
                business.
              </TooltipContent>
            </Tooltip>
          </span>
          <div className="relative w-8 h-8 flex items-center justify-center -mt-0.5">
            <svg className="w-8 h-8 transform -rotate-90">
              <circle
                className="text-zinc-200 dark:text-zinc-800"
                strokeWidth="2.5"
                stroke="currentColor"
                fill="transparent"
                r="14"
                cx="16"
                cy="16"
              />
              <circle
                className={
                  final_score >= 80
                    ? "text-emerald-500"
                    : final_score >= 60
                      ? "text-amber-500"
                      : "text-rose-500"
                }
                strokeWidth="2.5"
                strokeDasharray="100"
                strokeDashoffset={100 - final_score}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
                r="14"
                cx="16"
                cy="16"
                pathLength="100"
              />
            </svg>
            <span className="absolute text-[10px] font-mono font-bold text-zinc-800 dark:text-zinc-200">
              {final_score}
            </span>
          </div>
        </div>

        {/* Action button / Bookmark */}
        <div className="w-7 flex justify-center items-center">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleSave(influencer);
            }}
            title={isSaved ? "Remove from saved" : "Save lead"}
            className="p-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-all text-zinc-400 hover:text-amber-500"
          >
            <Bookmark
              size={15}
              className={isSaved ? "fill-amber-500 text-amber-500" : "text-zinc-400"}
            />
          </button>
        </div>
      </div>
    </div>
  );
};
