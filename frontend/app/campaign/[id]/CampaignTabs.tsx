"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface PageProps {
  id: string;
}

const CampaignTabs = ({ id }: PageProps) => {
  const pathname = usePathname();

  const navItems = [
    { name: "Details", path: "details" },
    { name: "Leads", path: "leads" },
    { name: "Saved", path: "saved" },
  ];

  return (
    <nav className="border-b border-neutral-200 dark:border-neutral-900 text-zinc-600 dark:text-zinc-400">
      <div className="px-16 flex items-center overflow-x-auto bg-white dark:bg-[#0c0d0e]">
        {navItems.map((item) => {
          const href = `/campaign/${id}/${item.path}`;
          const isActive = pathname === href;

          return (
            <Link
              key={item.name}
              href={href}
              className={`px-4 py-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                isActive
                  ? "text-neutral-900 dark:text-white border-b-black dark:border-b-white"
                  : "text-neutral-500 border-b-transparent hover:text-neutral-900 dark:hover:text-neutral-300"
              }`}
            >
              {item.name}
            </Link>
          );
        })}
      </div>
    </nav>
  );
};

export default CampaignTabs;