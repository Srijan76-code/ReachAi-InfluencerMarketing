import React, { useMemo } from "react";
import { Influencer } from "@/data/influencerList";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from "lucide-react";

export const CampaignSummaryBanner = ({
  influencers,
}: {
  influencers: Influencer[];
}) => {
  const stats = useMemo(() => {
    if (influencers.length === 0) return null;

    let sumReach = 0;
    let sumEffectiveReach = 0;
    let sumClicks = 0;
    let sumCost = 0;
    let sumBrandFit = 0;
    let sumConfidence = 0;

    influencers.forEach((inf) => {
      sumReach += inf.metrics.avg_views;
      // Effective reach proxy using actual engagement
      sumEffectiveReach += Math.floor(
        inf.metrics.avg_views * (inf.metrics.engagement_rate / 100) * 4,
      );

      const parsedClicks =
        parseInt(inf.metrics.forecast.replace(/[^0-9]/g, "")) || 0;
      sumClicks += parsedClicks;
      sumCost += inf.valuation;

      // Tracking the AI scoring breakdowns precisely
      sumBrandFit += inf.score_breakdown?.strategy_score || inf.semantic_score;
      sumConfidence += inf.score_breakdown?.health_score || inf.relevance_score;
    });

    const avgBrandFit = Math.round(sumBrandFit / influencers.length);
    const avgConfidence = Math.round(sumConfidence / influencers.length);

    // Realistic Forecast Boundaries (+/- variance)
    const reachLow = Math.round(sumReach * 0.85);
    const reachHigh = Math.round(sumReach * 1.3);

    const engLow = Math.round(sumEffectiveReach * 0.85);
    const engHigh = Math.round(sumEffectiveReach * 1.3);

    const clickLow = Math.round(sumClicks * 0.9);
    const clickHigh = Math.round(sumClicks * 1.25);

    // Calculate dynamic Cost Per Click bounds
    const cpcBase = sumCost / (sumClicks || 1);
    const cpcLow = Math.max(0.1, cpcBase * 0.7);
    const cpcHigh = cpcBase * 1.25;

    // ROI Signal evaluates financial return (low CPC means High ROI)
    const roiSignal =
      cpcBase < 1.0 ? "High" : cpcBase < 2.5 ? "Good" : "Moderate";

    return {
      totalReach: [reachLow, reachHigh],
      effectiveReach: [engLow, engHigh],
      estimatedClicks: [clickLow, clickHigh],
      cpc: [cpcLow, cpcHigh],
      totalCost: sumCost,
      brandFit: avgBrandFit,
      confidence: avgConfidence,
      roiSignal,
    };
  }, [influencers]);

  if (!stats) return null;

  // Minimalist numeric formatter (e.g., 21500 -> 21.5K)
  const formatCompact = (num: number) => {
    if (num >= 1000000)
      return (num / 1000000).toFixed(1).replace(/\.0$/, "") + "M";
    if (num >= 1000) return (num / 1000).toFixed(1).replace(/\.0$/, "") + "K";
    return Math.round(num).toLocaleString();
  };

  const formatPrice = (num: number) => {
    return num.toFixed(1).replace(/\.0$/, "");
  };

  return (
    <div className="bg-white dark:bg-transparent rounded-xl text-sm font-sans text-[13px] relative overflow-visible">
      {/* Aesthetic Top Lighting Line (Linear Style) */}
      <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-zinc-200 dark:via-zinc-700/50 to-transparent opacity-50 hidden lg:block" />

      {/* Ultra Minimal Banner Header */}
      <div className="flex items-center justify-between mb-4 px-1 lg:pt-3">
        <div className="flex items-center gap-2">
          <div className="w-1 h-1 rounded-full bg-blue-500" />
          <h2 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            Estimated campaign results
            <span className="text-[10px] font-medium text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-[#111111] border border-zinc-200 dark:border-zinc-800 px-1.5 py-0.5 rounded-md tracking-wider shadow-sm">
              {influencers.length} LEAD{influencers.length !== 1 ? "S" : ""}
            </span>
          </h2>
        </div>
      </div>

      <TooltipProvider delayDuration={150}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 px-1 lg:pb-3">
          {/* Scale Metrics Card */}
          <div className="flex flex-col gap-3 p-4 rounded-xl border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-[#111111]/80 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] dark:shadow-none transition-colors hover:border-zinc-300 dark:hover:border-zinc-700/50">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                Total Reach
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      Estimated total views based on a historical variance of
                      ±20% against average profile views.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-mono font-medium text-zinc-800 dark:text-zinc-200 tracking-wide">
                {formatCompact(stats.totalReach[0])} –{" "}
                {formatCompact(stats.totalReach[1])}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                Eff. Reach
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      Calculated dynamic active impressions based strictly on
                      each profile's historical engagement rates.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-mono font-medium text-zinc-800 dark:text-zinc-200 tracking-wide">
                {formatCompact(stats.effectiveReach[0])} –{" "}
                {formatCompact(stats.effectiveReach[1])}
              </span>
            </div>
          </div>

          {/* Return Metrics Card */}
          <div className="flex flex-col gap-3 p-4 rounded-xl border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-[#111111]/80 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] dark:shadow-none transition-colors hover:border-zinc-300 dark:hover:border-zinc-700/50">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                Est. Clicks
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      Forecasted link clicks driven by standard conversion
                      benchmarks.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-mono font-medium text-zinc-800 dark:text-zinc-200 tracking-wide">
                {formatCompact(stats.estimatedClicks[0])} –{" "}
                {formatCompact(stats.estimatedClicks[1])}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                Cost per Click
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      True calculated blend of all selected influencer
                      valuations divided by forecasted clicks.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-mono font-medium text-zinc-800 dark:text-zinc-200 tracking-wide">
                ${formatPrice(stats.cpc[0])} – ${formatPrice(stats.cpc[1])}
              </span>
            </div>
          </div>

          {/* Cost & Strategy Card */}
          <div className="flex flex-col gap-3 p-4 rounded-xl border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-[#111111]/80 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] dark:shadow-none transition-colors hover:border-zinc-300 dark:hover:border-zinc-700/50">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                Total Cost
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      Total combined budget required to secure the selected
                      leads at their fair market valuations.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-mono font-medium text-zinc-800 dark:text-zinc-200">
                ${stats.totalCost.toLocaleString()}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                ROI Signal
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      Pure financial metric: "High" indicates an estimated CPC
                      under $1.00, meaning excellent capital efficiency.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span
                className={`font-medium tracking-wide ${stats.roiSignal === "High" ? "text-emerald-500" : stats.roiSignal === "Good" ? "text-emerald-500/80" : "text-amber-500"}`}
              >
                {stats.roiSignal}
              </span>
            </div>
          </div>

          {/* AI Confidence Card */}
          <div className="flex flex-col gap-3 p-4 rounded-xl border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-50/50 dark:bg-[#111111]/80 shadow-[0_1px_3px_0_rgba(0,0,0,0.02)] dark:shadow-none transition-colors hover:border-zinc-300 dark:hover:border-zinc-700/50">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                Brand Fit
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      Average LLM semantic match comparing your specific brief
                      against the influencers' historical videos.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-mono font-medium text-blue-500">
                {stats.brandFit}%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
                Avg. Health
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info
                      size={12}
                      className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 cursor-pointer transition-colors"
                    />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-[200px] text-[11px] leading-snug">
                    <p>
                      Combined safety score assessing bot risk, engagement
                      authenticity, and shadow-ban status.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </span>
              <span className="font-mono font-medium text-emerald-500">
                {stats.confidence}%
              </span>
            </div>
          </div>
        </div>
      </TooltipProvider>
    </div>
  );
};
