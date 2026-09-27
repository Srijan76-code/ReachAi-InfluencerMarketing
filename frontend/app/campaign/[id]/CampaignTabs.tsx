"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  Search,
  Sun,
  LayoutGrid,
  Users,
  Bookmark,
  PlusCircle,
} from "lucide-react";
import { HoverButton } from "@/components/buttons/HoverButton";
import { useApi } from "@/lib/api";

interface PageProps {
  id: string;
}

const NAV_ITEMS = [
  { name: "Details", path: "details", icon: LayoutGrid },
  { name: "Leads", path: "leads", icon: Users },
  { name: "Saved", path: "saved", icon: Bookmark },
];

const CampaignTabs = ({ id }: PageProps) => {
  const pathname = usePathname();
  const router = useRouter();
  const api = useApi();

  const handleCreateNewCampaign = async () => {
    try {
      const res = await api("/api/campaigns/create", { method: "POST" });
      if (res.data && res.data.campaign_id) {
        router.push(`/campaign/${res.data.campaign_id}/details`);
      }
    } catch (err) {
      console.error("Error creating new campaign:", err);
      window.alert(
        err instanceof Error
          ? err.message
          : "Unable to create campaign. Please refresh and sign in again.",
      );
    }
  };

  return (
    <div className="fixed top-6 inset-x-0 bg-transparent z-30 h-16 flex px-0 pointer-events-none ">
      {/* --- LEFT SIDEBAR STRIP --- */}
      <div className="flex-1 h-10 dark:bg-[#08090a]  z-20 relative min-w-0 border-none">
        <svg
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="none"
        >
          <line
            x1="0"
            y1="39.5"
            x2="100%"
            y2="39.5"
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="0.5"
            className="text-zinc-500 dark:text-zinc-50"
          />
          <line
            x1="0"
            y1="36.5"
            x2="100%"
            y2="36.5"
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="0.5"
            className="text-zinc-500 dark:text-zinc-50"
          />
        </svg>
      </div>

      {/* --- CRADLE GROUP --- */}
      <div className="flex h-16 relative z-10 shrink-0 -ml-px pointer-events-auto">
        {/* Left Shoulder Transition */}
        <div className="w-[50px] h-full relative shrink-0">
          <div
            className="absolute inset-0 bg-zinc-50 dark:bg-[#08090a]"
            style={{ clipPath: "path('M0 0 H50 V64 C25 64 25 40 0 40 Z')" }}
          />
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox="0 0 50 64"
          >
            <path
              d="M0 39.5 C25 39.5 25 63.5 50 63.5"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.15"
              strokeWidth="0.5"
              className="text-zinc-500 dark:text-zinc-50"
            />
            <path
              d="M0 36.5 C25 36.5 25 60.5 50 60.5"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.15"
              strokeWidth="0.5"
              className="text-zinc-500 dark:text-zinc-50"
            />
          </svg>

        </div>

        {/* Center Content Area */}
        <div className="flex-1 h-full relative min-w-[500px] -ml-px dark:bg-[#08090a]  ">
          <div className="absolute dark:bg-[#08090a] inset-0 bg-zinc-50 ">
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              preserveAspectRatio="none"
            >
              <line
                x1="0"
                y1="63.5"
                x2="100%"
                y2="63.5"
                stroke="currentColor"
                strokeOpacity="0.15"
                strokeWidth="0.5"
                className="text-zinc-500 dark:text-zinc-50"
              />
              <line
                x1="0"
                y1="60.5"
                x2="100%"
                y2="60.5"
                stroke="currentColor"
                strokeOpacity="0.15"
                strokeWidth="0.5"
                className="text-zinc-500 dark:text-zinc-50"
              />
            </svg>
          </div>

          <div className="relative w-full h-full flex items-end justify-between pb-2.5 px-6">
            <nav className="flex items-center gap-6 mb-0.5 border-r pr-8 mb-1">
              {NAV_ITEMS.map((item) => {
                const href = `/campaign/${id}/${item.path}`;
                const isActive = pathname === href;
                return (
                  <Link
                    key={item.name}
                    href={href}
                    className={cn(
                      "group flex items-center gap-2 text-[13px] font-medium transition-colors whitespace-nowrap",
                      isActive
                        ? "text-zinc-900 dark:text-zinc-100"
                        : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100",
                    )}
                  >
                    <item.icon
                      size={15}
                      className={cn(
                        "opacity-70 group-hover:opacity-100",
                        isActive && "opacity-100",
                      )}
                    />
                    <span>{item.name}</span>
                    {/* {isActive && (
                      <motion.div 
                        layoutId="active-underline"
                        className="absolute -bottom-[10px] left-0 right-0 h-[1.5px] bg-zinc-900 dark:bg-zinc-100 z-50"
                      />
                    )} */}
                  </Link>
                );
              })}

            </nav>

            {/* <div className="flex text-xs justify-end items-center "> */}
            <HoverButton
              className="!bg-zinc-50 dark:!bg-[#08090a] z-50 border-neutral-200 dark:border-black text-neutral-900 dark:text-neutral-200 h-8 flex items-center justify-center px-3"
              glowColor="rgba(255, 255, 255, 0.2)"
              hoverTextColor="white"

              onClick={handleCreateNewCampaign}>
              <div className="flex justify-end items-center gap-2 text-xs">
                <PlusCircle className="w-3 h-3" />
                <p>New Campaign</p>
              </div>
            </HoverButton>
            {/* <div className="h-4 w-[1px] bg-zinc-200 dark:bg-zinc-800" /> */}
            {/* <button className="p-1.5 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                <Sun size={16} />
              </button> */}
            {/* </div> */}
          </div>
        </div>

        {/* Right Shoulder Transition */}
        <div className="w-[50px] h-ful dark:bg-[#08090a]  relative shrink-0 -ml-px">
          <div
            className="absolute inset-0 bg-zinc-50 dark:bg-[#08090a]"
            style={{ clipPath: "path('M0 0 H50 V40 C25 40 25 64 0 64 Z')" }}
          />
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox="0 0 50 64"
          >
            <path
              d="M0 63.5 C25 63.5 25 39.5 50 39.5"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.15"
              strokeWidth="0.5"
              className="text-zinc-500 dark:text-zinc-50"
            />
            <path
              d="M0 60.5 C25 60.5 25 36.5 50 36.5"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.15"
              strokeWidth="0.5"
              className="text-zinc-500 dark:text-zinc-50"
            />
          </svg>
        </div>
      </div>

      {/* --- RIGHT SIDEBAR STRIP --- */}
      <div className="flex-1 h-10 dark:bg-[#08090a]   z-20 relative min-w-0 -ml-px">
        <svg
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="none"
        >
          <line
            x1="0"
            y1="39.5"
            x2="100%"
            y2="39.5"
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="0.5"
            className="text-zinc-500 dark:text-zinc-50"
          />
          <line
            x1="0"
            y1="36.5"
            x2="100%"
            y2="36.5"
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="0.5"
            className="text-zinc-500 dark:text-zinc-50"
          />
        </svg>
      </div>
    </div>
  );
};

export default CampaignTabs;
