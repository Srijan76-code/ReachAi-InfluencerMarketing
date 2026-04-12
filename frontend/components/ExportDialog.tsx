"use client";

import React, { useState } from "react";
import { Download, ChevronRight } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
  DialogDescription
} from "@/components/ui/dialog";
import { Influencer } from "@/data/influencerList";
import { processExport, ExportConfig } from "@/lib/exportService";

export function ExportDialog({ influencers }: { influencers: Influencer[] }) {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<ExportConfig>({
    type: "outreach",
    format: "csv",
    template: "instantly",
    removeNoEmail: true,
    includeContext: false,
  });
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await processExport(influencers, config);
      setOpen(false);
    } catch (e) {
      console.error(e);
      alert("Export failed");
    } finally {
      setIsExporting(false);
    }
  };

  const getPreviewHeaders = () => {
    if (config.type === "raw") return ["id", "title", "platform", "country", "valuation"];
    if (config.template === "instantly") return ["email", "first_name", "company", "custom_1", "custom_2"];
    if (config.template === "smartlead") return ["email", "first_name", "icebreaker", "pitch", "cta"];
    return ["Channel Name", "Country", "Deal Status", "Email", "Instagram"];
  };

  const getPreviewRow = () => {
    if (config.type === "raw") return ["inf_18x92", "Krish Naik", "YouTube", "IN", "177"];
    if (config.template === "instantly") return ["krish@example.com", "Krish", "YouTube", "Really liked your content...", "We're running a campaign..."];
    if (config.template === "smartlead") return ["krish@example.com", "Krish", "Really liked your content...", "We're running a campaign...", "Would you be open..."];
    return ["Krish Naik", "IN", "Strong Buy", "krish@example.com", "@krishnaik"];
  };

  const DestinationRadio = ({ value, label, desc }: { value: string, label: string, desc: string }) => (
    <button onClick={() => setConfig({...config, type: "outreach", template: value as any})} className="flex items-start gap-2.5 group focus:outline-none text-left w-full p-1.5 hover:bg-zinc-50 dark:hover:bg-white/5 rounded-md transition-colors">
      <div className={`w-[14px] h-[14px] mt-[3px] rounded-full border flex items-center justify-center shrink-0 transition-colors ${config.type === "outreach" && config.template === value ? "border-zinc-900 dark:border-white bg-zinc-900 dark:bg-white" : "border-zinc-300 dark:border-zinc-700 bg-transparent group-hover:border-zinc-400 dark:group-hover:border-zinc-500"}`}>
        {config.type === "outreach" && config.template === value && <div className="w-[6px] h-[6px] rounded-full bg-white dark:bg-black" />}
      </div>
      <div className="flex flex-col gap-0.5">
        <span className={`text-[13px] font-medium transition-colors ${config.type === "outreach" && config.template === value ? "text-zinc-900 dark:text-[#ededed]" : "text-zinc-600 dark:text-[#a1a1aa] group-hover:text-zinc-900 dark:group-hover:text-[#ededed]"}`}>{label}</span>
        <span className="text-[11px] text-zinc-500">{desc}</span>
      </div>
    </button>
  );

  const CustomCheckbox = ({ checked, onChange, label }: { checked: boolean, onChange: () => void, label: string }) => (
    <button onClick={onChange} className="flex items-center gap-2.5 group focus:outline-none text-left py-1">
      <div className={`w-[14px] h-[14px] rounded-[3px] border flex items-center justify-center transition-colors shrink-0 ${checked ? "border-zinc-900 bg-zinc-900 dark:border-white dark:bg-white" : "border-zinc-300 dark:border-zinc-700 bg-transparent group-hover:border-zinc-400 dark:group-hover:border-zinc-500"}`}>
        {checked && <svg width="9" height="7" viewBox="0 0 9 7" fill="none" xmlns="http://www.w3.org/2000/svg" className="text-white dark:text-black"><path d="M1 3.5L3.5 6L8 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
      </div>
      <span className={`text-[13px] transition-colors ${checked ? "text-zinc-900 dark:text-[#ededed]" : "text-zinc-500 dark:text-[#a1a1aa] group-hover:text-zinc-700 dark:group-hover:text-zinc-300"}`}>{label}</span>
    </button>
  );

  const FormatRadio = ({ value, label }: { value: string, label: string }) => (
     <button onClick={() => setConfig({...config, format: value as any})} className="flex items-center gap-2.5 group focus:outline-none">
         <div className={`w-[14px] h-[14px] rounded-full border flex items-center justify-center transition-colors ${config.format === value ? "border-zinc-900 dark:border-white bg-zinc-900 dark:bg-white" : "border-zinc-300 dark:border-zinc-700 bg-transparent group-hover:border-zinc-400 dark:group-hover:border-zinc-500"}`}>
           {config.format === value && <div className="w-[6px] h-[6px] rounded-full bg-white dark:bg-black" />}
         </div>
         <span className={`text-[13px] transition-colors ${config.format === value ? "text-zinc-900 dark:text-[#ededed]" : "text-zinc-500 dark:text-[#a1a1aa] group-hover:text-zinc-700 dark:group-hover:text-zinc-300"}`}>{label}</span>
     </button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors focus:outline-none">
          <Download size={14} />
          Export Leads
        </button>
      </DialogTrigger>
      
      <DialogContent className="sm:max-w-[480px] p-0 overflow-hidden bg-white dark:bg-[#0a0a0a] border-zinc-200 dark:border-white/10 shadow-2xl rounded-xl font-sans">
        
        {/* Header */}
        <div className="px-5 py-4 border-b border-zinc-200 dark:border-white/5">
          <DialogTitle className="text-[15px] font-medium text-zinc-900 dark:text-[#ededed]">Export Data</DialogTitle>
          <DialogDescription className="text-[13px] text-zinc-500 dark:text-[#a1a1aa] mt-1">
            Generate files ready for immediate outreach deployment.
          </DialogDescription>
        </div>

        <div className="p-5 space-y-7">
          
          {/* 1. Export Destination */}
          <div className="space-y-2">
            <label className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">Export Destination</label>
            <div className="flex flex-col gap-1 -ml-1.5">
              <DestinationRadio value="instantly" label="Instantly (Cold Email)" desc="Strict email mappings with custom variable slots." />
              <DestinationRadio value="smartlead" label="Smartlead (Cold Email)" desc="Semantic variable mappings for icebreakers/offers." />
              <DestinationRadio value="generic" label="Generic CSV" desc="Standard export containing full influencer profile." />
            </div>
          </div>

          {/* 2. Options */}
          <div className="space-y-2">
            <label className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">Options</label>
            <div className="flex flex-col">
              <CustomCheckbox 
                checked={config.removeNoEmail} 
                onChange={() => setConfig({...config, removeNoEmail: !config.removeNoEmail})} 
                label="Only include leads with email"
              />
              <CustomCheckbox 
                checked={config.includeContext} 
                onChange={() => setConfig({...config, includeContext: !config.includeContext})} 
                label="Include performance metrics (views, engagement, pricing)"
              />
            </div>
          </div>

          {/* 3. Format */}
          <div className="space-y-2.5">
             <label className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">Format</label>
             <div className="flex items-center gap-6">
                <FormatRadio value="csv" label="Standard CSV" />
                <FormatRadio value="excel" label="Excel (.xlsx)" />
             </div>
          </div>

          {/* 4. Column Preview (Safe Boundary Layout) */}
          <div className="space-y-2">
             <div className="flex items-center justify-between">
                <label className="text-[12px] font-medium text-zinc-900 dark:text-[#ededed]">Payload Preview</label>
             </div>
             <div className="rounded-md border border-zinc-200 dark:border-white/10 bg-white dark:bg-[#0c0d0e] flex flex-col w-full overflow-hidden shadow-sm">
                 <div className="flex w-full items-center border-b border-zinc-200 dark:border-white/5 bg-zinc-50 dark:bg-white/[0.02]">
                    {getPreviewHeaders().slice(0, 3).map((h, i) => (
                       <div key={i} className="flex-1 min-w-0 px-3 py-1.5 text-[10px] font-medium text-zinc-500 dark:text-[#a1a1aa] truncate border-r border-zinc-200 dark:border-white/5 last:border-r-0">
                         {h}
                       </div>
                    ))}
                 </div>
                 <div className="flex w-full items-center">
                    {getPreviewRow().slice(0, 3).map((c, i) => (
                       <div key={i} className="flex-1 min-w-0 px-3 py-2 text-[11px] font-mono text-zinc-800 dark:text-[#ededed] truncate border-r border-zinc-200 dark:border-white/5 last:border-r-0">
                         {c}
                       </div>
                    ))}
                 </div>
             </div>
             <p className="text-[10px] text-zinc-400 dark:text-zinc-600 text-right">+ {getPreviewHeaders().length - 3} additional mapped columns</p>
          </div>

          {/* 5. Advanced Settings */}
          <details className="group [&_summary::-webkit-details-marker]:hidden pt-2">
             <summary className="flex items-center gap-1.5 cursor-pointer text-[12px] font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-[#ededed] transition-colors focus:outline-none">
               <ChevronRight size={12} className="transition-transform group-open:rotate-90" />
               Advanced Settings
             </summary>
             <div className="pt-3 pl-5">
                <CustomCheckbox 
                  checked={config.type === "raw"} 
                  onChange={() => setConfig({...config, type: config.type === "raw" ? "outreach" : "raw"})} 
                  label="Raw Data Export (Bypass Pipeline Formatting)"
                />
             </div>
          </details>

        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-zinc-200 dark:border-white/5 bg-zinc-50/50 dark:bg-[#0a0a0a] flex items-center justify-between mt-auto">
           <button 
             onClick={() => setOpen(false)}
             className="px-4 py-2 text-[13px] font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white transition-colors focus:outline-none"
           >
             Cancel
           </button>
           <button 
             onClick={handleExport}
             disabled={isExporting}
             className="px-4 py-2 text-[13px] font-medium bg-zinc-900 hover:bg-zinc-800 dark:bg-[#ededed] dark:hover:bg-white disabled:opacity-50 text-white dark:text-black rounded-md transition-all shadow-sm focus:outline-none flex items-center gap-2"
           >
             {isExporting ? "Processing..." : "Download Export"}
             {!isExporting && <Download size={14} className="opacity-70" />}
           </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
