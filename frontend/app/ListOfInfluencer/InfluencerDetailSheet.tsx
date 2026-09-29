import { 
  SheetContent, 
  SheetTitle,
  SheetClose
} from "@/components/ui/sheet";
import { 
  ShieldCheck, 
  MousePointerClick, 
  Sparkles, 
  PlayCircle, 
  DollarSign, 
  Mail, 
  Instagram, 
  Twitter, 
  Info,
  Activity,
  Globe,
  ExternalLink,
  X,
  Target,
  TrendingUp,
  BarChart2,
  Users,
  Eye
} from "lucide-react";
import { 
  Tooltip, 
  TooltipContent, 
  TooltipProvider, 
  TooltipTrigger 
} from "@/components/ui/tooltip";
import type { Influencer } from "@/data/influencerList";

export const InfluencerDetailSheet = ({ influencer }: { influencer: Influencer }) => {
  const { metrics, socials, title, deal_status, score_breakdown } = influencer;

  // Status Color Logic
  const statusStyles = {
    "Strong Buy": "text-emerald-500 border-emerald-500/20 bg-emerald-500/10",
    "Consider": "text-amber-500 border-amber-500/20 bg-amber-500/10",
    "Avoid": "text-rose-500 border-rose-500/20 bg-rose-500/10",
  };

  return (
    <TooltipProvider delayDuration={200}>
      <SheetContent className="sm:max-w-[560px] bg-white dark:bg-[#0c0d0e] border-l border-zinc-200/80 dark:border-zinc-800/80 p-0 text-zinc-700 dark:text-zinc-300 flex flex-col h-full font-sans shadow-2xl">
        
        {/* --- HEADER --- */}
        <div className="p-6 border-b border-zinc-200/60 dark:border-zinc-800/60 flex flex-col gap-6 relative shrink-0 bg-zinc-50 dark:bg-[#08090a]">
          {/* <SheetClose className="absolute right-6 top-6 rounded-sm opacity-50 transition-opacity hover:opacity-100 focus:outline-none">
            <X size={18} className="text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors" />
            <span className="sr-only">Close</span>
          </SheetClose> */}

          <div className="flex items-start justify-between pr-8">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-300 dark:border-zinc-700/50 flex items-center justify-center text-lg font-medium text-zinc-600 dark:text-zinc-400 shrink-0">
                {title[0].toUpperCase()}
              </div>
              
              <div className="flex flex-col gap-2 pt-0.5">
                <div className="flex items-center gap-3">
                  <SheetTitle className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 leading-none">
                    {title}
                  </SheetTitle>
                  <span className={`px-2 py-0.5 rounded border text-[10px] font-medium ${statusStyles[deal_status]}`}>
                    {deal_status}
                  </span>
                </div>
                
                <div className="flex items-center gap-2.5 text-[12px] text-zinc-500">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Globe size={13} className="text-zinc-500" /> Youtube Creator
                  </span>
                  <span className="w-1 h-1 rounded-full bg-zinc-200 dark:bg-zinc-700" />
                  <span className="font-medium text-zinc-600 dark:text-zinc-400 tracking-wide">{influencer.country.toUpperCase()}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-2">
              <a href={socials.instagram || "#"} className="w-8 h-8 rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-center hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"><Instagram size={14} /></a>
              <a href={socials.twitter || "#"} className="w-8 h-8 rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-center hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"><Twitter size={14} /></a>
              <a href={`mailto:${socials.email || ""}`} className="w-8 h-8 rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-center hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"><Mail size={14} /></a>
            </div>
            <button className="bg-zinc-100 hover:bg-zinc-900 dark:hover:bg-white text-zinc-900 text-[12px] font-semibold px-4 py-2 rounded transition-colors shadow-sm active:scale-95">
              Start Outreach
            </button>
          </div>
        </div>

        {/* --- MAIN SCROLLABLE CONTENT --- */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar bg-white dark:bg-[#0c0d0e]">
          
          {/* AI REASONING */}
          <section className="space-y-3">
            <div className="flex items-center justify-between pr-2">
              <div className="flex items-center gap-1.5">
                <h3 className="text-[11px] font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                  <Sparkles size={14} className="text-emerald-500" />
                  Campaign Fit Analysis
                </h3>
                <Tooltip>
                  <TooltipTrigger asChild><Info size={12} className="text-zinc-400 dark:text-zinc-600 cursor-help hover:text-zinc-600 dark:hover:text-zinc-400 transition-colors" /></TooltipTrigger>
                  <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs shadow-xl max-w-[220px] text-zinc-700 dark:text-zinc-300">
                     Read this to understand exactly why the AI believes this creator matches your specific campaign brief and target audience.
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="flex items-center gap-2 bg-zinc-100 dark:bg-zinc-800/30 px-2 py-1 rounded-full border border-zinc-200/60 dark:border-zinc-700/50">
                <span className="text-[9px] font-bold tracking-widest uppercase text-zinc-600 dark:text-zinc-400 pl-1">Impact</span>
                <div className="relative w-6 h-6 flex items-center justify-center">
                  <svg className="w-6 h-6 transform -rotate-90">
                    <circle className="text-zinc-200 dark:text-zinc-800" strokeWidth="2.5" stroke="currentColor" fill="transparent" r="10" cx="12" cy="12" />
                    <circle 
                      className={influencer.final_score >= 80 ? "text-emerald-500" : influencer.final_score >= 60 ? "text-amber-500" : "text-rose-500"} 
                      strokeWidth="2.5" 
                      strokeDasharray="100" 
                      strokeDashoffset={100 - Math.round(influencer.final_score)} 
                      strokeLinecap="round" 
                      stroke="currentColor" 
                      fill="transparent" 
                      r="10" 
                      cx="12" 
                      cy="12" 
                      pathLength="100" 
                    />
                  </svg>
                  <span className="absolute text-[8px] font-mono font-bold text-zinc-900 dark:text-zinc-200">{Math.round(influencer.final_score)}</span>
                </div>
              </div>
            </div>
            <p className="text-[13px] text-zinc-700 dark:text-zinc-300 leading-relaxed pl-4 border-l-2 border-zinc-200 dark:border-zinc-800 py-0.5">
              {influencer.llm_reasoning}
            </p>
          </section>

          {/* BRAND FIT SCORING */}
          <hr className="border-zinc-200/80 dark:border-zinc-800/60" />
          <section className="space-y-3">
            <h3 className="text-[11px] font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider flex items-center gap-2">
              <Target size={14} className="text-blue-500" />
              Intelligence Diagnostics
            </h3>
            <div className="grid grid-cols-2 gap-4">
              
              <div className="space-y-2.5 bg-zinc-100 dark:bg-[#121314] p-3.5 rounded border border-zinc-200/60 dark:border-zinc-800/60">
                 <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">Brand Fit</span>
                      <Tooltip>
                        <TooltipTrigger asChild><Info size={12} className="text-zinc-400 dark:text-zinc-600 cursor-help hover:text-zinc-600 dark:hover:text-zinc-400 transition-colors" /></TooltipTrigger>
                        <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs shadow-xl max-w-[200px] text-zinc-700 dark:text-zinc-300">Tells you how perfectly this creator matches your specific campaign goals.</TooltipContent>
                      </Tooltip>
                    </div>
                    <span className="text-[12px] font-mono font-medium text-zinc-600 dark:text-zinc-400">{score_breakdown.strategy_score}%</span>
                 </div>
                 <div className="h-1 w-full bg-zinc-100/80 dark:bg-zinc-800/80 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full" style={{ width: `${score_breakdown.strategy_score}%` }} />
                 </div>
              </div>

              <div className="space-y-2.5 bg-zinc-100 dark:bg-[#121314] p-3.5 rounded border border-zinc-200/60 dark:border-zinc-800/60">
                 <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">Health</span>
                      <Tooltip>
                        <TooltipTrigger asChild><Info size={12} className="text-zinc-400 dark:text-zinc-600 cursor-help hover:text-zinc-600 dark:hover:text-zinc-400 transition-colors" /></TooltipTrigger>
                        <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs shadow-xl max-w-[200px] text-zinc-700 dark:text-zinc-300">Tells you if their audience is authentic and safe from bots or fake engagement.</TooltipContent>
                      </Tooltip>
                    </div>
                    <span className="text-[12px] font-mono font-medium text-zinc-600 dark:text-zinc-400">{score_breakdown.health_score}%</span>
                 </div>
                 <div className="h-1 w-full bg-zinc-100/80 dark:bg-zinc-800/80 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${score_breakdown.health_score}%` }} />
                 </div>
              </div>

            </div>
          </section>

          {/* ROI METRICS GRID */}
          <section className="space-y-3">
            <h3 className="text-[11px] font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider flex items-center gap-2">
              <BarChart2 size={14} className="text-indigo-400" />
              Performance Metrics
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 rounded border border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-100 dark:bg-[#121314] overflow-hidden">
               <MetricCell 
                label="Subscribers" 
                value={`${(influencer.subscribers / 1000).toFixed(1)}k`} 
                icon={<Users size={13}/>} 
                info="Total channel audience size."
              />
               <MetricCell 
                label="Avg Views" 
                value={`${(metrics.avg_views / 1000).toFixed(1)}k`} 
                icon={<Eye size={13}/>} 
                info="Average views per video."
              />
               <MetricCell 
                label="Engagement" 
                value={`${metrics.engagement_rate}%`} 
                icon={<Target size={13}/>} 
                info="Tells you if the audience cares. Higher numbers mean they are highly likely to listen to the creator."
                removeBorderRight
              />
               <MetricCell 
                label="Trust Score" 
                value={`${metrics.trust_score}%`} 
                icon={<ShieldCheck size={13}/>} 
                info="Tells you if their audience is genuine and highly engaged."
                borderTop
              />
               <MetricCell 
                label="Fair Value" 
                value={`$${influencer.valuation}`} 
                icon={<DollarSign size={13}/>} 
                info="The exact budget you need to set aside to sponsor 1 video."
                valueColorClass="text-rose-500 dark:text-rose-400 font-mono text-[14px]"
                borderTop
              />
               <MetricCell 
                label="Yield" 
                value={metrics.forecast.split(' ')[0]} 
                icon={<MousePointerClick size={13}/>} 
                info="The estimated number of people who will click your link to buy or sign up."
                borderTop
                removeBorderRight
                valueColorClass="text-emerald-500 dark:text-emerald-400 font-mono text-[14px]"
              />
            </div>
          </section>

          {/* RECENT PERFORMANCE LIST */}
          <hr className="border-zinc-200/80 dark:border-zinc-800/60" />
          <section className="space-y-3 pb-6">
            <div className="flex items-center justify-between">
              <h3 className="text-[11px] font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider flex items-center gap-2">
                <PlayCircle size={14} className="text-amber-500" />
                Recent Content
              </h3>
              <a href="#" className="text-[11px] font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors flex items-center gap-1 group">
                Full Analytics <ExternalLink size={11} className="group-hover:translate-x-0.5 transition-transform" />
              </a>
            </div>
            
            <div className="rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-100 dark:bg-[#121314] overflow-hidden divide-y divide-zinc-800/60">
              {influencer.recent_videos.slice(0, 5).map((video, i) => (
                <div key={i} className="flex items-center justify-between p-3 hover:bg-zinc-100/30 dark:hover:bg-zinc-800/30 transition-colors group cursor-pointer">
                  <div className="flex items-center gap-3 overflow-hidden">
                    <PlayCircle size={14} className="text-zinc-400 dark:text-zinc-600 group-hover:text-zinc-600 dark:group-hover:text-zinc-400 shrink-0 transition-colors" />
                    <span className="text-[12px] text-zinc-700 dark:text-zinc-300 truncate group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors">{video.title}</span>
                  </div>
                  <span className="font-mono text-[11px] text-zinc-500 shrink-0 ml-4 group-hover:text-zinc-600 dark:group-hover:text-zinc-400 transition-colors">
                    {(video.views / 1000).toFixed(1)}k
                  </span>
                </div>
              ))}
            </div>
          </section>

        </div>
      </SheetContent>
    </TooltipProvider>
  );
};

// --- HELPER COMPONENT FOR METRICS GRID ---
const MetricCell = ({ label, value, icon, info, borderTop, removeBorderRight, valueColorClass }: any) => (
  <div className={`p-3.5 flex flex-col gap-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800/20 transition-colors
    ${borderTop ? 'border-t border-zinc-200/60 dark:border-zinc-800/60' : ''} 
    ${!removeBorderRight ? 'border-r border-zinc-200/60 dark:border-zinc-800/60' : ''}
  `}>
    <div className="flex items-center gap-1.5 text-zinc-500">
      <span className="text-zinc-400 dark:text-zinc-600">{icon}</span>
      <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">{label}</span>
      {info && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Info size={11} className="text-zinc-400 dark:text-zinc-600 hover:text-zinc-600 dark:hover:text-zinc-400 cursor-help transition-colors" />
          </TooltipTrigger>
          <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs shadow-xl max-w-[200px] text-zinc-700 dark:text-zinc-300">
             {info}
          </TooltipContent>
        </Tooltip>
      )}
    </div>
    <span className={`text-[13px] font-semibold truncate pl-[1.125rem] ${valueColorClass || "text-zinc-900 dark:text-zinc-200"}`}>{value}</span>
  </div>
);