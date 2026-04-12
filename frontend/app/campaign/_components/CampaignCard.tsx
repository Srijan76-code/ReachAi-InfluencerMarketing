"use client";

import { MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
type CampaignStatus = "draft" | "active" | "completed";

interface CampaignCardProps {
  name: string;
  step: string;
  updatedAt: string;
  status?: CampaignStatus;
  onEdit?: () => void;
  onDelete?: () => void;
  onOpen?: () => void;
}

export default function CampaignCard({
  name,
  step,
  updatedAt,
  status = "draft",
  onEdit,
  onDelete,
  onOpen,
}: CampaignCardProps) {


  const statusMap: Record<CampaignStatus, string> = {
    draft: "Draft",
    active: "Active",
    completed: "Completed",
  };

  const statusColor: Record<CampaignStatus, string> = {
    draft: "text-neutral-500 border-neutral-300/50",
    active: "text-blue-400 border-blue-400/30",
    completed: "text-emerald-400 border-emerald-400/30",
  };

  return (
    <div
   
      onClick={onOpen}
      className="
     group cursor-pointer
     border border-neutral-200/60 dark:border-neutral-800
     rounded-xl
     bg-white dark:bg-[#0c0d0e]
     p-5
     transition-colors duration-200
     hover:border-neutral-300 dark:hover:border-neutral-700
   "
    >
      {/* Top Row */}{" "}
      <div className="flex items-start justify-between">
        {" "}
        <div className="flex items-start gap-3 min-w-0">
          {/* Avatar */}
          <div
            className="
        h-9 w-9 shrink-0
        rounded-md
        bg-neutral-100 dark:bg-neutral-900
        border border-neutral-200 dark:border-neutral-800
        flex items-center justify-center
        text-sm font-medium
        text-neutral-700 dark:text-neutral-300
      "
          >
            {name?.charAt(0).toUpperCase()}
          </div>

          {/* Content */}
          <div className="min-w-0">
            {/* Title + Status */}
            <div className="flex items-center gap-2">
              <h3
                className="
            text-[15px] font-semibold tracking-tight
            text-neutral-900 dark:text-white
            truncate
          "
              >
                {name}
              </h3>

              <span
                className={`
            text-[11px] font-medium px-2 py-[2px] rounded-md border
            ${statusColor[status]}
          `}
              >
                {statusMap[status]}
              </span>
            </div>

            {/* Step */}
            <p
              className="
          mt-1 text-[13px] font-medium
          text-neutral-700 dark:text-neutral-300
        "
            >
              {step}
            </p>
          </div>
        </div>
        {/* Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => e.stopPropagation()}
              className="
            h-8 w-8
            text-neutral-500
            hover:text-neutral-700 dark:hover:text-neutral-300
            hover:bg-neutral-100 dark:hover:bg-neutral-900
          "
            >
              <MoreHorizontal size={16} />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onEdit?.();
              }}
              className="text-[13px] font-medium"
            >
              Edit Campaign
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation();
                onDelete?.();
              }}
              className="text-[13px] font-medium text-red-400 focus:text-red-400"
            >
              Delete Campaign
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {/* Footer */}
      <div
        className="
    mt-4 text-[12px]
    text-neutral-500
  "
      >
        Updated{" "}
        <span className="text-neutral-700 dark:text-neutral-400 font-medium">
          {updatedAt}
        </span>
      </div>
    </div>
  );
}
