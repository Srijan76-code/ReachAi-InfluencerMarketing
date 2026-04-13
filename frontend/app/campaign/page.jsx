"use client"
import { useState } from "react"
import VercelNavbar from "../../components/VercelNavbar"
import CampaignCard from "./_components/CampaignCard"
import { DemoCampaigns } from "@/data/BrandDashboard/DemoCampaigns"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { ListFilterIcon, ArrowUpDown } from "lucide-react"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useRouter } from "next/navigation";

const CampaignPage = () => {
  const router = useRouter()

  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [sortBy, setSortBy] = useState("none")
  const campaigns = DemoCampaigns

  const filteredCampaigns = campaigns
    .filter(campaign => {
      const matchesSearch = campaign.name.toLowerCase().includes(searchQuery.toLowerCase())
      const matchesStatus = statusFilter === "all" || campaign.status.toLowerCase() === statusFilter.toLowerCase()
      return matchesSearch && matchesStatus
    })
    .sort((a, b) => {
      if (sortBy === "asc") {
        return new Date(a.createdAt) - new Date(b.createdAt)
      } else if (sortBy === "desc") {
        return new Date(b.createdAt) - new Date(a.createdAt)
      }
      return 0
    })

  return (
    <div className=" bg-zinc-50 dark:bg-[#08090a] text-neutral-900 dark:text-neutral-200">
     
      {/* <div>
        <div className="px-6 py-4 font-raleway max-w-[1400px] mx-auto flex items-center gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search campaigns by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-white dark:bg-[#0c0d0e] border-neutral-200 dark:border-neutral-800 text-neutral-900 dark:text-neutral-200 placeholder-neutral-500 w-full text-[14px]"
            />
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="outline"
                className="cursor-pointer bg-white dark:bg-[#0c0d0e] border-neutral-200 dark:border-neutral-800 text-neutral-700 dark:text-neutral-200 hover:bg-neutral-50 dark:hover:bg-neutral-900"
              >
                <ListFilterIcon className=" h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-48 bg-white dark:bg-[#0c0d0e] border-neutral-200 dark:border-neutral-800" align="start">
              <DropdownMenuLabel className="text-neutral-500 dark:text-neutral-400 text-xs uppercase tracking-wider">Status</DropdownMenuLabel>
              <DropdownMenuItem 
                className={`cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 ${statusFilter === "all" ? "bg-neutral-50 dark:bg-neutral-800 font-medium" : ""}`}
                onClick={() => setStatusFilter("all")}
              >
                All
              </DropdownMenuItem>
              <DropdownMenuItem 
                className={`cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 ${statusFilter === "active" ? "bg-neutral-50 dark:bg-neutral-800 font-medium" : ""}`}
                onClick={() => setStatusFilter("active")}
              >
                Active
              </DropdownMenuItem>
              <DropdownMenuItem 
                className={`cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 ${statusFilter === "in progress" ? "bg-neutral-50 dark:bg-neutral-800 font-medium" : ""}`}
                onClick={() => setStatusFilter("in progress")}
              >
                In progress
              </DropdownMenuItem>
              <DropdownMenuItem 
                className={`cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 ${statusFilter === "draft" ? "bg-neutral-50 dark:bg-neutral-800 font-medium" : ""}`}
                onClick={() => setStatusFilter("draft")}
              >
                Draft
              </DropdownMenuItem>
              <DropdownMenuSeparator className="bg-neutral-200 dark:bg-neutral-800" />
              <DropdownMenuLabel className="text-neutral-500 dark:text-neutral-400 text-xs uppercase tracking-wider">Sort by</DropdownMenuLabel>
              <DropdownMenuItem 
                className={`cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 flex justify-between items-center ${sortBy === "asc" ? "bg-neutral-50 dark:bg-neutral-800 font-medium" : ""}`}
                onClick={() => setSortBy(sortBy === "asc" ? "none" : "asc")}
              >
                <span>Created At Asc</span>
                <ArrowUpDown className="h-4 w-4" />
              </DropdownMenuItem>
              <DropdownMenuItem 
                className={`cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 flex justify-between items-center ${sortBy === "desc" ? "bg-neutral-50 dark:bg-neutral-800 font-medium" : ""}`}
                onClick={() => setSortBy(sortBy === "desc" ? "none" : "desc")}
              >
                <span>Created At Desc</span>
                <ArrowUpDown className="h-4 w-4" />
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button 
            variant="default"
            className="bg-black hover:bg-neutral-800 dark:bg-white dark:hover:bg-neutral-200 text-white dark:text-black cursor-pointer text-[13px] font-medium"
          >
            Create Campaign
          </Button>
        </div>
      </div> */}
      <div className="px-6 py-16 font-raleway max-w-[1400px] mx-auto">
        {filteredCampaigns.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center rounded-xl border border-dashed border-neutral-200 dark:border-neutral-800 bg-white dark:bg-[#0c0d0e] text-neutral-500">
            <p className="text-[14px] font-medium text-neutral-900 dark:text-neutral-200">No campaigns found</p>
            <p className="text-[13px] text-neutral-500 dark:text-neutral-500 mt-1">Try adjusting your search or create a new campaign.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredCampaigns.map((campaign) => (
              <CampaignCard
                key={campaign.id}
                logoUrl={campaign.logoUrl}
                name={campaign.name}
                step={campaign.step}
                status={campaign.status}
                updatedAt={campaign.createdAt}
                onEdit={() => console.log("edit", campaign.id)}
                onDelete={() => console.log("delete", campaign.id)}
                 onOpen={() => router.push(`/campaign/${campaign.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default CampaignPage