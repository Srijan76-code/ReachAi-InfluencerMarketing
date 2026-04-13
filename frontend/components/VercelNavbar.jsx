import {
  Search,
  Bell,
  BookOpen,
  Menu,
  Settings,
  CreditCard,
  Building,
  Home,
  LogOut,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NavbarData } from "@/data/VercelNavbar/DemoNavbar";
// import { Feedback } from "@/components/ui/feedback"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skiper26 } from "./ui/skiper-ui/skiper26";
import Link from "next/link";
import { HoverButton } from "./buttons/HoverButton";

export default function Dashboard() {
  return (
    <div className="bg-white dark:bg-[#0c0d0e] text-neutral-900 dark:text-neutral-200 border-b border-neutral-200 dark:border-neutral-800 font-raleway  ">
      {/* Header */}
      <header>
        <div className="flex h-16 items-center justify-between px-6">
          {/* Left section */}
          <div className="flex items-center gap-6">
            <div className="text-black dark:text-white text-xl font-bold">
              ▲
            </div>
            <div className="h-5 w-px bg-neutral-200 dark:bg-neutral-800 rotate-30"></div>
            {NavbarData?.map((item, idx) => (
              <div key={idx} className="flex items-center gap-2">
                {item.logo ? (
                  <img
                    src={item.logo}
                    alt={item.organisationName || "Logo"}
                    className="w-5 h-5 rounded-full shadow-[0_0_0_2px_rgba(9,9,9,0.9)] object-cover"
                  />
                ) : (
                  <div className="w-5 h-5 rounded-full bg-cyan-500 shadow-[0_0_0_2px_rgba(255,255,255,0.9)] dark:shadow-[0_0_0_2px_rgba(9,9,9,0.9)]"></div>
                )}
                <span  className="text-sm font-medium text-neutral-600 dark:text-neutral-300">
                  {item.organisationName}'s campaigns
                </span>
              </div>
            ))}
          </div>

          {/* Right section */}
          <div className="flex items-center gap-6">
            {/* <Button
                            variant="outline"
                            size="sm"
                            className="bg-black dark:bg-black border border-neutral-800 dark:border-neutral-800 text-neutral-300 hover:text-neutral-100 hover:bg-neutral-900 dark:hover:bg-neutral-900 cursor-pointer"
                        >
                            Feedback
                        </Button> */}

            {/* <Feedback label="Feedback" /> */}
            <div className="">
              <Skiper26 />
            </div>

            <Link href="/campaign/1234/details">
              <HoverButton>
                <div className="flex gap-2 items-center">
                  <Users className="w-4 h-4" />
                  <p>New Campaign</p>
                </div>
              </HoverButton>
            </Link>

            {/* <button className="text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200 transition-colors">
              <Bell size={20} />
            </button>
            <button className="text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200 transition-colors">
              <BookOpen size={20} />
            </button> */}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <div className="cursor-pointer w-8 h-8 rounded-full bg-linear-to-br from-orange-500 via-pink-500 to-purple-500 shadow-[0_0_0_2px_rgba(12,12,12,0.7)]"></div>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-56 bg-white dark:bg-[#0c0d0e] border-neutral-200 dark:border-neutral-800"
                align="start"
              >
                {NavbarData?.map((item, idx) => (
                  <div key={idx}>
                    <DropdownMenuLabel className="text-sm font-medium text-neutral-900 dark:text-neutral-200">
                      {item.organisationName}
                    </DropdownMenuLabel>
                    <DropdownMenuLabel className="text-xs text-neutral-500 dark:text-neutral-400 truncate max-w-[200px]">
                      {item.organisationEmail}
                    </DropdownMenuLabel>
                  </div>
                ))}
                <DropdownMenuSeparator className="bg-neutral-200 dark:bg-neutral-800" />
                <DropdownMenuItem className="cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 flex justify-between items-center">
                  <span>Account settings</span>
                  <Settings className="h-4 w-4" />
                </DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 flex justify-between items-center">
                  <span>Billing and Payments</span>
                  <CreditCard className="h-4 w-4" />
                </DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 flex justify-between items-center">
                  <span>Workspace</span>
                  <Building className="h-4 w-4" />
                </DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 flex justify-between items-center">
                  <span>Home Page</span>
                  <Home className="h-4 w-4" />
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-neutral-200 dark:bg-neutral-800" />
                <DropdownMenuItem className="cursor-pointer text-[13px] text-neutral-700 dark:text-neutral-200 hover:bg-neutral-100 dark:hover:bg-neutral-900 focus:bg-neutral-100 dark:focus:bg-neutral-900 flex justify-between items-center">
                  <span>Logout</span>
                  <LogOut className="h-4 w-4" />
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Navigation */}
      {/* <nav className="border-b border-neutral-200 dark:border-neutral-900">
                <div className="px-6 flex items-center overflow-x-auto">
                    {navItems.map((item, index) => (
                        <button
                            key={item}
                            className={`px-4 py-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${index === 0
                                ? "text-neutral-900 dark:text-white border-b-black dark:border-b-white"
                                : "text-neutral-500 border-b-transparent hover:text-neutral-900 dark:hover:text-neutral-300"
                                }`}
                        >
                            {item}
                        </button>
                    ))}
                </div>
            </nav> */}
    </div>
  );
}
