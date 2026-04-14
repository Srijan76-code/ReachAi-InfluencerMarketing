"use client"

import { MoreHorizontal } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

import { Campaign, CampaignStatus } from "@/types/campaign"

type CampaignCardProps = {
  campaign: Campaign
  onEdit?: () => void
  onDelete?: () => void
  onOpen?: () => void
}

export default function CampaignCard({
  campaign,
  onEdit,
  onDelete,
  onOpen,
}: CampaignCardProps) {
  const { name, step, createdAt, status } = campaign

  // 🔥 deterministic gradient (feels like identity)
  const gradients = [
    "from-indigo-500/20 to-indigo-500/5",
    "from-blue-500/20 to-blue-500/5",
    "from-purple-500/20 to-purple-500/5",
    "from-emerald-500/20 to-emerald-500/5",
  ]

  const gradient = gradients[name.length % gradients.length]

  const statusMap: Record<CampaignStatus, string> = {
    draft: "Draft",
    active: "Active",
    in_progress: "In Progress",
  }

  const statusStyle: Record<CampaignStatus, string> = {
    draft: "text-neutral-400 bg-neutral-500/10 border-neutral-500/20",
    active: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    in_progress: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  }

  return (
    <div
      onClick={onOpen}
      className="
        group cursor-pointer
        rounded-xl
        border border-neutral-200/60 dark:border-neutral-800
        bg-white dark:bg-[#0c0d0e]
        p-5
        transition-all duration-200
        hover:border-neutral-300 dark:hover:border-neutral-700
        hover:shadow-[0_0_0_1px_rgba(255,255,255,0.02)]
      "
    >
      {/* Top */}
      <div className="flex items-start justify-between">
        
        <div className="flex items-start gap-3 min-w-0">

          {/* 🔥 Gradient Avatar */}
          <div
            className={`
              h-10 w-10 shrink-0 rounded-lg
              bg-gradient-to-br ${gradient}
              border border-white/10
              flex items-center justify-center
              text-sm font-semibold
              text-white/80
              backdrop-blur-md
            `}
          >
            {name.charAt(0).toUpperCase()}
          </div>

          {/* Content */}
          <div className="min-w-0">
            
            {/* Title + Status */}
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-medium tracking-tight text-neutral-900 dark:text-white truncate">
                {name}
              </h3>

              <span
                className={`
                  text-[10.5px] px-2 py-[2px]
                  rounded-md border font-medium
                  ${statusStyle[status]}
                `}
              >
                {statusMap[status]}
              </span>
            </div>

            {/* Step */}
            <p className="mt-1 text-[10px] text-neutral-500 dark:text-neutral-400 font-medium">
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
                
                text-neutral-400
                hover:text-neutral-600 dark:hover:text-neutral-300
                hover:bg-neutral-100 dark:hover:bg-neutral-900
              "
            >
              <MoreHorizontal size={16} />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onEdit?.() }}>
              Edit Campaign
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              onClick={(e) => { e.stopPropagation(); onDelete?.() }}
              className="text-red-400"
            >
              Delete Campaign
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Footer */}
      <div className="mt-4 text-[10px] text-neutral-500">
        Updated{" "}
        <span className="text-neutral-700 dark:text-neutral-300 font-medium">
          {createdAt}
        </span>
      </div>
    </div>
  )
}