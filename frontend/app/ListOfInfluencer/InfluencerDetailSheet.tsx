"use client";

import { useState } from "react";
import type React from "react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { FeedbackSection } from "@/components/Feedback";
import { AddToDealsButton } from "@/components/deals/AddToDealsButton";
import type { FeedbackItem } from "@/data/influencerList";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

const PLATFORM_NAMES: Record<string, string> = { youtube: "YouTube", instagram: "Instagram", x: "X", linkedin: "LinkedIn" };

/** A bigger version of a profile photo: YouTube photo links carry their size (=s88), so ask for 800px. */
function largePhoto(url?: string | null): string | undefined {
  if (!url) return undefined;
  return /=s\d+/.test(url) ? url.replace(/=s\d+/, "=s800") : url;
}
import { CreatorBadges, badgeFlags } from "@/components/CreatorBadges";
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
  Eye,
  Send,
  BadgeCheck,
  TrendingDown,
  Minus,
} from "lucide-react";
import { ScoreParts } from "@/components/ScoreParts";
import { PostTabs } from "@/components/PostTabs";
import { freshness, trendLabel } from "@/lib/posts";
import { 
  Tooltip, 
  TooltipContent, 
  TooltipProvider, 
  TooltipTrigger 
} from "@/components/ui/tooltip";
import type { Influencer } from "@/data/influencerList";
import { OutreachDialog } from "@/components/OutreachDialog";

export const InfluencerDetailSheet = ({
  influencer,
  campaignId,
  readOnly = false,
  feedback,
  reviewSlot,
}: {
  influencer: Influencer;
  campaignId?: string;
  readOnly?: boolean; // shared view: no contacts, no outreach
  feedback?: FeedbackItem[]; // owner's view: what reviewers said
  reviewSlot?: React.ReactNode; // shared view for reviewers: their 👍/👎 and comment
}) => {
  const { metrics, socials, title, deal_status, score_breakdown } = influencer;
  // the creator's channel: stored URL (new engine) or built from the channel id (older results)
  const channelUrl = influencer.url || `https://www.youtube.com/channel/${influencer.id}`;
  const platformName = PLATFORM_NAMES[(influencer.platform || "youtube").toLowerCase()] ?? "their channel";
  const [photoOpen, setPhotoOpen] = useState(false);
  const fresh = influencer.data_expired ? null : freshness(influencer.data_as_of);
  const trend = influencer.data_expired ? null : trendLabel(influencer.trend);
  const parts = influencer.score_parts && typeof influencer.score_parts.fit === "number" ? influencer.score_parts : null;
  const posts = influencer.data_expired ? [] : influencer.posts ?? [];

  // Status Color Logic
  const statusStyles = {
    "Strong Buy": "text-emerald-500 border-emerald-500/20 bg-emerald-500/10",
    "Consider": "text-amber-500 border-amber-500/20 bg-amber-500/10",
    "Avoid": "text-rose-500 border-rose-500/20 bg-rose-500/10",
    "Added by you": "text-zinc-600 dark:text-zinc-400 border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800/50",
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
              {influencer.avatar_url ? (
                <button
                  type="button"
                  onClick={() => setPhotoOpen(true)}
                  aria-label={`Open ${title}'s photo`}
                  title="Open photo"
                  className="shrink-0 rounded cursor-zoom-in focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
                >
                  <CreatorAvatar
                    name={title}
                    src={influencer.avatar_url}
                    className="w-12 h-12 rounded bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-300 dark:border-zinc-700/50 flex items-center justify-center text-lg font-medium text-zinc-600 dark:text-zinc-400 shrink-0 hover:opacity-90 transition-opacity"
                  />
                </button>
              ) : (
                <CreatorAvatar
                  name={title}
                  src={influencer.avatar_url}
                  className="w-12 h-12 rounded bg-zinc-100 dark:bg-zinc-800/50 border border-zinc-300 dark:border-zinc-700/50 flex items-center justify-center text-lg font-medium text-zinc-600 dark:text-zinc-400 shrink-0"
                />
              )}
              <Dialog open={photoOpen} onOpenChange={setPhotoOpen}>
                <DialogContent className="sm:max-w-sm p-3 bg-white dark:bg-[#0c0d0e]">
                  <DialogTitle className="sr-only">{title}</DialogTitle>
                  {/* eslint-disable-next-line @next/next/no-img-element -- remote platform photo */}
                  <img src={largePhoto(influencer.avatar_url)} alt={title} referrerPolicy="no-referrer" className="w-full aspect-square object-cover rounded-md bg-zinc-100 dark:bg-zinc-900" />
                  <a href={channelUrl} target="_blank" rel="noopener noreferrer" className="text-center text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:underline">
                    {title} on {platformName}
                  </a>
                </DialogContent>
              </Dialog>
              
              <div className="flex flex-col gap-2 pt-0.5">
                <div className="flex items-center gap-3">
                  <SheetTitle className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 leading-none">
                    <a href={channelUrl} target="_blank" rel="noopener noreferrer" className="hover:underline underline-offset-4 decoration-zinc-300 dark:decoration-zinc-600" title="Open channel">
                      {title}
                    </a>
                  </SheetTitle>
                  {influencer.verified && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <BadgeCheck size={16} className="text-blue-500 shrink-0 -ml-1.5" aria-label="Verified" />
                      </TooltipTrigger>
                      <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs text-zinc-700 dark:text-zinc-300">
                        Verified by the platform
                      </TooltipContent>
                    </Tooltip>
                  )}
                  <span className={`px-2 py-0.5 rounded border text-[10px] font-medium ${statusStyles[deal_status]}`}>
                    {deal_status}
                  </span>
                </div>
                <CreatorBadges flags={badgeFlags(influencer)} size="md" />
                {influencer.data_expired && (
                  <p className="text-[12px] text-zinc-500">
                    This creator&apos;s YouTube numbers are over 30 days old, so they were removed. Run the campaign again for fresh numbers.
                  </p>
                )}
                
                <div className="flex items-center gap-2.5 text-[12px] text-zinc-500">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Globe size={13} className="text-zinc-500" /> {influencer.platform === "youtube" || !influencer.platform ? "YouTube" : influencer.platform} creator
                  </span>
                  <span className="w-1 h-1 rounded-full bg-zinc-200 dark:bg-zinc-700" />
                  <span
                    className="font-medium text-zinc-600 dark:text-zinc-400 tracking-wide"
                    title={influencer.country_source === "jev" ? "YouTube doesn't list a country for this channel, so Jev judged its audience's country from the posts" : undefined}
                  >
                    {influencer.country ? influencer.country.toUpperCase() : "Country unknown"}
                    {influencer.country && influencer.country_source === "jev" && (
                      <span className="ml-1 font-normal tracking-normal text-zinc-500">· judged from their posts</span>
                    )}
                  </span>
                  {fresh && (
                    <>
                      <span className="w-1 h-1 rounded-full bg-zinc-200 dark:bg-zinc-700" />
                      <span title={influencer.data_as_of ? new Date(influencer.data_as_of).toLocaleString() : undefined}>{fresh}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {!readOnly && (
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-2">
              <SocialLink href={socials.instagram} label="Instagram" className="w-8 h-8 rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-center hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"><Instagram size={14} /></SocialLink>
              <SocialLink href={socials.twitter} label="X" className="w-8 h-8 rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-center hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"><Twitter size={14} /></SocialLink>
              <SocialLink href={socials.email ? `mailto:${socials.email}` : null} label="Email" external={false} className="w-8 h-8 rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-center hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"><Mail size={14} /></SocialLink>
            </div>
            {readOnly ? null : campaignId ? (
              <div className="flex items-center gap-2">
              <AddToDealsButton campaignId={campaignId} creatorIds={[influencer.id]} />
              <OutreachDialog
                campaignId={campaignId}
                influencers={[influencer]}
                trigger={
                  <button className="bg-zinc-900 hover:bg-zinc-800 text-white dark:bg-white dark:hover:bg-zinc-100 dark:text-zinc-900 text-[12px] font-medium px-4 py-2 rounded-md transition-colors shadow-sm active:scale-95 flex items-center gap-1.5">
                    <Send size={12} />
                    Start Outreach
                  </button>
                }
              />
              </div>
            ) : (
              <a href="/sign-in" title="Sign in to contact creators" className="bg-zinc-100 hover:bg-zinc-900 hover:text-white dark:hover:bg-white dark:hover:text-zinc-900 text-zinc-900 text-[12px] font-semibold px-4 py-2 rounded transition-colors shadow-sm active:scale-95">
                Start Outreach
              </a>
            )}
          </div>
          )}
        </div>

        {/* --- MAIN SCROLLABLE CONTENT --- */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar bg-white dark:bg-[#0c0d0e]">
          
          {/* AI REASONING */}
          <section className="space-y-3">
            <div className="flex items-center justify-between pr-2">
              <div className="flex items-center gap-1.5">
                <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <Sparkles size={14} className="text-emerald-500" />
                  Campaign fit
                </h3>
                <Tooltip>
                  <TooltipTrigger asChild><Info size={12} className="text-zinc-400 dark:text-zinc-600 cursor-help hover:text-zinc-600 dark:hover:text-zinc-400 transition-colors" /></TooltipTrigger>
                  <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs shadow-xl max-w-[220px] text-zinc-700 dark:text-zinc-300">
                     Read this to understand exactly why the AI believes this creator matches your specific campaign brief and target audience.
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="flex items-center gap-2 bg-zinc-100 dark:bg-zinc-800/30 px-2 py-1 rounded-full border border-zinc-200/60 dark:border-zinc-700/50">
                <span className="text-[11px] font-medium text-zinc-600 dark:text-zinc-400 pl-1">Impact</span>
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

          {reviewSlot}
          <FeedbackSection items={feedback} />

          {/* POSTS: the evidence right after the fit analysis */}
          <hr className="border-zinc-200/80 dark:border-zinc-800/60" />
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <PlayCircle size={14} className="text-amber-500" />
                {posts.length > 0 ? "Posts" : "Recent content"}
              </h3>
              <a href={platformName === "YouTube" ? `${channelUrl}/videos` : channelUrl} target="_blank" rel="noopener noreferrer" className="text-[11px] font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200 transition-colors flex items-center gap-1 group">
                View on {platformName} <ExternalLink size={11} className="group-hover:translate-x-0.5 transition-transform" />
              </a>
            </div>
            
            {posts.length > 0 ? (
              <PostTabs posts={posts} signals={influencer.signals} fallbackUrl={`${channelUrl}/videos`} />
            ) : (
              <div className="rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-100 dark:bg-[#121314] overflow-hidden divide-y divide-zinc-800/60">
                {influencer.recent_videos.slice(0, 5).map((video, i) => (
                  <a key={i} href={video.url || `${channelUrl}/videos`} target="_blank" rel="noopener noreferrer" title={video.url ? "Watch on YouTube" : "Open the channel's videos"} className="flex items-center justify-between p-3 hover:bg-zinc-100/30 dark:hover:bg-zinc-800/30 transition-colors group cursor-pointer">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <PlayCircle size={14} className="text-zinc-400 dark:text-zinc-600 group-hover:text-zinc-600 dark:group-hover:text-zinc-400 shrink-0 transition-colors" />
                      <span className="text-[12px] text-zinc-700 dark:text-zinc-300 truncate group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors">{video.title}</span>
                    </div>
                    <span className="font-mono text-[11px] text-zinc-500 shrink-0 ml-4 group-hover:text-zinc-600 dark:group-hover:text-zinc-400 transition-colors">
                      {(video.views / 1000).toFixed(1)}k
                    </span>
                  </a>
                ))}
              </div>
            )}
          </section>
          {/* METRICS */}
          <hr className="border-zinc-200/80 dark:border-zinc-800/60" />
          <section className="space-y-3">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <BarChart2 size={14} className="text-indigo-400" />
              Performance
              {trend && (
                <span
                  title="Views on their newest posts compared with the ones before"
                  className={`ml-auto normal-case tracking-normal font-medium text-[11px] flex items-center gap-1 ${trend.tone === "up" ? "text-emerald-600 dark:text-emerald-400" : trend.tone === "down" ? "text-rose-500" : "text-zinc-500"}`}
                >
                  {trend.tone === "up" ? <TrendingUp size={12} /> : trend.tone === "down" ? <TrendingDown size={12} /> : <Minus size={12} />}
                  Views {trend.text.toLowerCase()}
                </span>
              )}
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
                value={metrics.avg_views == null ? "—" : `${(metrics.avg_views / 1000).toFixed(1)}k`}
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
                value={influencer.valuation == null ? "No price yet" : `$${influencer.valuation}`}
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

          {/* WHY THIS SCORE: detail for whoever wants it */}
          <hr className="border-zinc-200/80 dark:border-zinc-800/60" />
          <section className="space-y-3 pb-6">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <Target size={14} className="text-blue-500" />
              Why this score
            </h3>
            {parts && (
              <div className="space-y-2">
                <ScoreParts parts={parts} finalScore={influencer.final_score} />
              </div>
            )}
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


        </div>
      </SheetContent>
    </TooltipProvider>
  );
};

// --- A social icon: a real link when we have it, a dimmed "not found" icon when we don't ---
const SocialLink = ({ href, label, className, children, external = true }: {
  href?: string | null; label: string; className: string; children: React.ReactNode; external?: boolean;
}) =>
  href ? (
    <a href={href} aria-label={label} title={label} className={className} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
      {children}
    </a>
  ) : (
    <span aria-disabled="true" title={`No ${label} found`} className={`${className} opacity-40 cursor-not-allowed pointer-events-auto`}>
      {children}
    </span>
  );

// --- HELPER COMPONENT FOR METRICS GRID ---
const MetricCell = ({ label, value, icon, info, borderTop, removeBorderRight, valueColorClass }: any) => (
  <div className={`p-3.5 flex flex-col gap-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800/20 transition-colors
    ${borderTop ? 'border-t border-zinc-200/60 dark:border-zinc-800/60' : ''} 
    ${!removeBorderRight ? 'border-r border-zinc-200/60 dark:border-zinc-800/60' : ''}
  `}>
    <div className="flex items-center gap-1.5 text-zinc-500">
      <span className="text-zinc-400 dark:text-zinc-600">{icon}</span>
      <span className="text-[11px] font-medium text-zinc-500">{label}</span>
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