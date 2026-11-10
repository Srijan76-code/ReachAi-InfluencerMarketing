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

import { Campaign, CampaignStatus, updatedLabel } from "@/types/campaign"

type CampaignCardProps = {
  campaign: Campaign
  onRename?: () => void
  onDelete?: () => void
  onOpen?: () => void
}

const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: "Draft",
  running: "Searching",
  ready: "Ready",
  empty: "No creators",
  failed: "Failed",
}

const STATUS_STYLE: Record<CampaignStatus, string> = {
  draft: "text-neutral-400 bg-neutral-500/10 border-neutral-500/20",
  running: "text-amber-500 bg-amber-500/10 border-amber-500/20",
  ready: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
  empty: "text-neutral-400 bg-neutral-500/10 border-neutral-500/20",
  failed: "text-rose-500 bg-rose-500/10 border-rose-500/20",
}

function subtitle(c: Campaign): string {
  switch (c.status) {
    case "ready":
      return `${c.leadsCount} creator${c.leadsCount === 1 ? "" : "s"} found`
    case "running":
      return "Finding creators…"
    case "empty":
      return "Try a wider brief"
    case "failed":
      return "Open to retry"
    default:
      return "Brief not finished"
  }
}

export default function CampaignCard({ campaign, onRename, onDelete, onOpen }: CampaignCardProps) {
  const { name, status, updatedAt } = campaign

  // deterministic gradient per name (an identity colour)
  const gradients = [
    "from-indigo-500/20 to-indigo-500/5",
    "from-blue-500/20 to-blue-500/5",
    "from-purple-500/20 to-purple-500/5",
    "from-emerald-500/20 to-emerald-500/5",
  ]
  const gradient = gradients[name.length % gradients.length]

  return (
    <div
      onClick={onOpen}
      role="link"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter") onOpen?.() }}
      className="
        group cursor-pointer
        rounded-xl
        border border-neutral-200/60 dark:border-neutral-800
        bg-white dark:bg-[#0c0d0e]
        p-5
        transition-all duration-200
        hover:border-neutral-300 dark:hover:border-neutral-700
        hover:shadow-[0_0_0_1px_rgba(255,255,255,0.02)]
        focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-neutral-400
      "
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3 min-w-0">
          <div
            className={`
              h-10 w-10 shrink-0 rounded-lg
              bg-gradient-to-br ${gradient}
              border border-white/10
              flex items-center justify-center
              text-sm font-semibold
              text-neutral-700 dark:text-white/80
              backdrop-blur-md
            `}
          >
            {name.charAt(0).toUpperCase()}
          </div>

          <div className="min-w-0">
            <h3 className="text-xs font-medium tracking-tight text-neutral-900 dark:text-white line-clamp-2 break-words" title={name}>
              {name}
            </h3>
            <div className="mt-1.5 flex items-center gap-2 min-w-0">
              <span className={`shrink-0 whitespace-nowrap text-[10.5px] px-2 py-[2px] rounded-md border font-medium ${STATUS_STYLE[status]}`}>
                {STATUS_LABEL[status]}
              </span>
              <p className="text-[10px] text-neutral-500 dark:text-neutral-400 font-medium truncate">
                {subtitle(campaign)}
              </p>
            </div>
          </div>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Actions for ${name}`}
              onClick={(e) => e.stopPropagation()}
              className="h-8 w-8 shrink-0 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900"
            >
              <MoreHorizontal size={16} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40" onClick={(e) => e.stopPropagation()}>
            <DropdownMenuItem onSelect={() => onRename?.()}>Rename</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => onDelete?.()} className="text-red-500 focus:text-red-500">
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="mt-4 text-[10px] text-neutral-500" title={new Date(updatedAt).toLocaleString()}>
        Updated <span className="text-neutral-700 dark:text-neutral-300 font-medium">{updatedLabel(updatedAt)}</span>
      </div>
    </div>
  )
}
