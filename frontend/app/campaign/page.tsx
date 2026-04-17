"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowBigDown,
  ArrowDown,
  ArrowDownCircle,
  ArrowDownWideNarrow,
  ArrowUp,
  ArrowUpAZ,
  ArrowUpWideNarrow,
  Plus,
  PlusCircle,
  Search,
  SlidersHorizontal,
  SlidersVertical,
} from "lucide-react";

import CampaignCard from "./_components/CampaignCard";
import { DemoCampaigns } from "@/data/BrandDashboard/DemoCampaigns";
import { Campaign, CampaignStatus } from "@/types/campaign";
import { Input } from "@/components/ui/input";
import { HoverButton } from "@/components/buttons/HoverButton";
import { useApi } from "@/lib/api";

type StatusFilter = "all" | CampaignStatus;
type SortOption = "none" | "asc" | "desc";

const CampaignPage: React.FC = () => {
  const api = useApi();
  const router = useRouter();

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortBy, setSortBy] = useState<SortOption>("none");

    useEffect(() => {
    const init = async () => {
      try {

        const res = await api("/api/campaigns/", {
          method: "GET",
        });

        console.log("Campaigns:", res.data);

      } catch (err) {
        console.error(err);
      }
    };

    init();
  }, []);


  const campaigns: Campaign[] = DemoCampaigns;

  const filteredCampaigns = campaigns
    .filter((c) => {
      const matchesSearch = c.name
        .toLowerCase()
        .includes(searchQuery.toLowerCase());

      const matchesStatus = statusFilter === "all" || c.status === statusFilter;

      return matchesSearch && matchesStatus;
    })
    .sort((a, b) => {
      if (sortBy === "asc") {
        return (
          new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        );
      }
      if (sortBy === "desc") {
        return (
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      }
      return 0;
    });




  const statuses: { label: string; value: StatusFilter }[] = [
    { label: "All Campaigns", value: "all" },
    { label: "Active", value: "active" },
    { label: "Draft", value: "draft" },
    { label: "In Progress", value: "in_progress" },
  ];





  return (
    <div className="min-h-[calc(100vh-64px)] mt-16 border-t border-zinc-200 dark:border-neutral-800/80 bg-zinc-50 dark:bg-[#08090a] text-neutral-900 dark:text-neutral-200">
      <div className="px-6 pt-10 pb-24 max-w-7xl mx-auto">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 ">
          <div>
            <h1 className=" font-medium tracking-tight text-neutral-900 dark:text-neutral-200">
              Campaigns
            </h1>
            <p className="mt-1 text-[12px] text-neutral-500 dark:text-neutral-400">
              Manage and track your influencer campaigns.
            </p>
          </div>
        </div>

        {/* Filters / Toolbar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 my-8 border-b border-neutral-200 dark:border-neutral-800/80 pb-6 ">
          {/* Status Tabs */}
          <div className="flex items-center p-[3px] bg-zinc-50 dark:bg-[#08090a] rounded-lg border border-neutral-200/60 dark:border-neutral-800/80 w-full sm:w-auto overflow-x-auto hide-scrollbar">
            {statuses.map((status) => (
              <button
                key={status.value}
                onClick={() => setStatusFilter(status.value)}
                className={`
                  px-4 py-1 text-xs font-medium rounded-md transition-all whitespace-nowrap
                  ${
                    statusFilter === status.value
                      ? "bg-white dark:bg-[#1f2023] text-neutral-900 dark:text-neutral-100 shadow-sm border border-neutral-200/50 dark:border-white/5"
                      : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 hover:bg-neutral-200/50 dark:hover:bg-neutral-800/50"
                  }
                `}
              >
                {status.label}
              </button>
            ))}
          </div>

          <div className="flex gap-4">
            {/* Search & Sort */}
            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <button
                className="flex items-center justify-center h-8 w-8 shrink-0 bg-zinc-50 dark:bg-[#08090a] border border-neutral-200 dark:border-neutral-800/80 rounded-lg shadow-sm hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                onClick={() =>
                  setSortBy(
                    sortBy === "desc"
                      ? "asc"
                      : sortBy === "asc"
                        ? "none"
                        : "desc",
                  )
                }
              >
                <ArrowDownWideNarrow
                  size={14}
                  className={
                    sortBy !== "none"
                      ? "text-neutral-900 dark:text-white"
                      : "text-neutral-400"
                  }
                />
              </button>
              <div className="relative w-full sm:w-64">
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400"
                  size={14}
                />
                <Input
                  placeholder="Search campaigns..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 h-8 w-full bg-zinc-50 dark:bg-[#08090a] border-neutral-200 dark:border-neutral-800/80 text-xs rounded-lg shadow-sm focus-visible:ring-1 focus-visible:ring-neutral-400 dark:focus-visible:ring-neutral-600 transition-all placeholder:text-neutral-500"
                />
              </div>
            </div>
            {/* New Campaign button */}

            <HoverButton
              onClick={() => router.push("/campaign/")}
              className="!bg-zinc-50 dark:!bg-[#08090a] border-neutral-200 dark:border-neutral-800/80 text-neutral-900 dark:text-neutral-200 rounded-lg shadow-sm h-8 flex items-center justify-center px-3"
              glowColor="rgba(255, 255, 255, 0.2)"
              hoverTextColor="white"
            >
              <div className="flex gap-2 text-xs py-0.5 items-center">
                <PlusCircle className="w-3 h-3" />
                <p>New Campaign</p>
              </div>
            </HoverButton>
          </div>
        </div>

        {/* Content */}
        {filteredCampaigns.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center border border-dashed border-neutral-200 dark:border-neutral-800 rounded-xl bg-white/50 dark:bg-[#0c0d0e]/50">
            <div className="h-12 w-12 rounded-full bg-neutral-100 dark:bg-neutral-800 flex items-center justify-center mb-4">
              <Search className="text-neutral-400" size={24} />
            </div>
            <h3 className="text-sm font-medium text-neutral-900 dark:text-white">
              No campaigns found
            </h3>
            <p className="text-sm text-neutral-500 mt-1">
              Try adjusting your filters or search query.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 pt-4">
            {filteredCampaigns.map((campaign) => (
              <CampaignCard
                key={campaign.id}
                campaign={campaign}
                onOpen={() => router.push(`/campaign/${campaign.id}`)}
                onEdit={() => console.log("edit", campaign.id)}
                onDelete={() => console.log("delete", campaign.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CampaignPage;
