"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { AnimatePresence, motion } from "motion/react";
import { useInbox } from "@/lib/inbox";
import {
  LayoutGrid,
  Users,
  Send,
  Handshake,
} from "lucide-react";

interface PageProps {
  id: string;
}

// One tab per step of a campaign (max 5: Brief, Creators, Outreach, Deals, then Results when it
// ships). Things that span campaigns (New campaign, Docs, account) live in the main navbar.
const NAV_ITEMS = [
  { name: "Brief", path: "details", icon: LayoutGrid },
  { name: "Creators", path: "leads", icon: Users },
  { name: "Outreach", path: "outreach", icon: Send },
  { name: "Deals", path: "deals", icon: Handshake },
];

const CampaignTabs = ({ id }: PageProps) => {
  const pathname = usePathname();
  const waiting = useInbox().by_campaign[id];


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
            <nav className="flex items-center gap-6 mb-1 mx-auto">
              {NAV_ITEMS.map((item) => {
                const href = `/campaign/${id}/${item.path}`;
                const isActive = pathname === href || pathname?.startsWith(`${href}/`);
                return (
                  <Link
                    key={item.name}
                    href={href}
                    className={cn(
                      "relative group flex items-center gap-2 text-[13px] font-medium transition-colors whitespace-nowrap",
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
                    <AnimatePresence>
                      {item.path === "deals" && waiting && (waiting.unread || waiting.waiting) > 0 && (
                        <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={{ type: "spring", stiffness: 500, damping: 25 }}
                          aria-label={`${waiting.unread || waiting.waiting} waiting`}
                          className={`min-w-4 h-4 px-1 rounded-full text-[10px] font-medium flex items-center justify-center ${waiting.unread ? "bg-blue-500 text-white" : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"}`}>
                          {waiting.unread || waiting.waiting}
                        </motion.span>
                      )}
                    </AnimatePresence>
                    {isActive && (
                      // slides between tabs instead of jumping
                      <motion.span
                        layoutId="campaign-tab-underline"
                        className="absolute -bottom-[7px] left-0 right-0 h-[1.5px] rounded-full bg-zinc-900 dark:bg-zinc-100"
                        aria-hidden
                      />
                    )}
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
