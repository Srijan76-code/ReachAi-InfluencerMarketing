"use client";

import React from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { InfluencerRow } from "./InfluencerRow";
import { final_ranked_leads } from "@/data/influencerList";
import {
  ListFilter,
  ArrowUpDown,
  Download,
  ChevronDown,
  FileSpreadsheet,
  FileText,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"; // Assuming Shadcn Dropdown
import { Sheet, SheetTrigger } from "@/components/ui/sheet";
import { InfluencerDetailSheet } from "./InfluencerDetailSheet";

const InfluencerPage = () => {
  return (
    <TooltipProvider delayDuration={150}>
      <div className="min-h-screen bg-zinc-50 dark:bg-[#08090a] text-zinc-600 dark:text-zinc-400 p-8 font-sans selection:bg-blue-500/30">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* --- HEADER SECTION --- */}
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              Influencer Leads
            </h1>
            <span className="text-xs font-medium text-zinc-500 bg-zinc-100/50 dark:bg-zinc-800/50 border border-zinc-300/50 dark:border-zinc-700/50 px-2 py-0.5 rounded-full">
              {final_ranked_leads.length}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Sort & Filter */}
            <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors">
              <ArrowUpDown size={14} />
              Sort
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors">
              <ListFilter size={14} />
              Filter
            </button>

            {/* Export Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-zinc-900 dark:text-white rounded-md transition-colors shadow-lg shadow-blue-500/10">
                  <Download size={14} />
                  Export
                  <ChevronDown size={12} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400"
              >
                <DropdownMenuItem className="gap-2 focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer">
                  <FileText size={14} />
                  Export as CSV
                </DropdownMenuItem>
                <DropdownMenuItem className="gap-2 focus:bg-zinc-100 dark:focus:bg-zinc-800 focus:text-zinc-900 dark:focus:text-zinc-100 cursor-pointer">
                  <FileSpreadsheet size={14} />
                  Export as XLSX
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* --- INFLUENCER LIST --- */}
        <div className="flex flex-col gap-2">
          {/* gap-2 provides the subtle spacing between rows like in the image */}
          {final_ranked_leads.map((influencer) => (
            <Sheet key={influencer.id}>
              <SheetTrigger asChild>
                <div className="rounded-lg border border-zinc-200/50 dark:border-zinc-800/50 overflow-hidden cursor-pointer hover:border-zinc-300/50 dark:hover:border-zinc-700/50 transition-colors">
                  <InfluencerRow influencer={influencer} />
                </div>
              </SheetTrigger>
              <InfluencerDetailSheet influencer={influencer} />
            </Sheet>
          ))}
        </div>
      </div>
      </div>
    </TooltipProvider>
  );
};

export default InfluencerPage;
