"use client";

import { usePathname } from "next/navigation";

import {
    Breadcrumb,
    BreadcrumbItem,
    BreadcrumbLink,
    BreadcrumbList,
    BreadcrumbPage,
    BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

export default function BreadCumb() {
    const pathname = usePathname();

    const isHome = pathname === "/";
    const isCampaigns = pathname.startsWith("/campaign");

    return (
        <Breadcrumb>
            <BreadcrumbList>
                {/* ReachAI */}
                <BreadcrumbItem>
                    {isHome ? (
                        <BreadcrumbPage className="flex items-center gap-2">
                            <div className="w-7 h-7 bg-zinc-900 dark:bg-white rounded-lg flex items-center justify-center">
                                <div className="w-2 h-2 bg-white dark:bg-zinc-900 rounded-sm" />
                            </div>

                            <span className=" text-sm tracking-tighter">
                                ReachAI
                            </span>
                        </BreadcrumbPage>
                    ) : (
                        <BreadcrumbLink
                            href="/"
                            className="flex items-center gap-2 group"
                        >
                            <div className="w-4 h-4 bg-zinc-900 dark:bg-white rounded-sm flex items-center justify-center group-hover:rotate-6 transition-transform">
                                <div className="w-1.5 h-1.5 bg-white dark:bg-zinc-900 rounded-sm" />
                            </div>

                            <span  className="text-sm">
                                ReachAI
                            </span>
                        </BreadcrumbLink>
                    )}
                </BreadcrumbItem>

                <BreadcrumbSeparator>/</BreadcrumbSeparator>

                {/* Campaigns */}
                <BreadcrumbItem>
                    {isCampaigns ? (
                        <BreadcrumbPage className="text-sm font-medium">
                            Campaigns
                        </BreadcrumbPage>
                    ) : (
                        <BreadcrumbLink
                            href="/campaign"
                            className="text-sm"
                        >
                            Campaigns
                        </BreadcrumbLink>
                    )}
                </BreadcrumbItem>
            </BreadcrumbList>
        </Breadcrumb>
    );
}