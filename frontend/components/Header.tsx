"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Github, ArrowRight, PlusCircle, HomeIcon } from "lucide-react";
import { cn } from "@/lib/utils"; // standard shadcn helper
import { Skiper26 } from "./ui/skiper-ui/skiper26";
import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import BreadCumb from "./BreadCumb";
import { HoverButton } from "./buttons/HoverButton";
import { useRouter } from "next/navigation";

const NAV_LINKS = [
  { name: "Features", href: "#features" },
  { name: "Solutions", href: "#solutions" },
  { name: "Resources", href: "#resources" },
  { name: "Pricing", href: "#pricing" },
];

export default function Header() {
  const router = useRouter();
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="dark:bg-[#08090a] z-50 fixed top-0 inset-x-0  h-2">

      <nav
        className={cn(
          "fixed top-2   inset-x-0 z-40 h-10 transition-all duration-300  dark:bg-[#08090a]",

        )}
      >
        <div className="max-w-7xl mx-auto h-full px-6 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-7 h-7 bg-zinc-900 dark:bg-neutral-300 rounded-lg flex items-center justify-center group-hover:rotate-6 transition-transform">
              <div className="w-3 h-3 bg-white dark:bg-zinc-900 rounded-sm" />
            </div>
            <span className="font-bold text-sm tracking-tighter text-zinc-900 dark:text-zinc-100">
              ReachAI
            </span>
          </Link>
          {/* <BreadCumb /> */}

          {/* Desktop Navigation */}
          {/* <div className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.name}
              href={link.href}
              className="text-[13px] font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
            >
              {link.name}
            </Link>
          ))}
        </div> */}

          {/* Actions */}
          <div className="hidden md:flex items-center gap-4">
            {/* <button className="p-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
            <Github size={18} />
          </button> */}
            {/* <Skiper26/> */}



            <Show when="signed-out">
              <SignInButton>
                <button className="text-[13px] font-medium text-zinc-600 dark:text-zinc-400 px-4 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-full transition-all">
                  Log in
                </button>
              </SignInButton>

              <SignUpButton>
                <button className="group text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-4 py-1.5 rounded-full flex items-center gap-1.5 hover:opacity-90 transition-all shadow-sm">
                  Sign up
                  <ArrowRight
                    size={14}
                    className="group-hover:translate-x-0.5 transition-transform"
                  />
                </button>
              </SignUpButton>
            </Show>

            <Show when="signed-in">
              <HoverButton
                onClick={() => router.push("/campaign")}
                className="!bg-zinc-50 dark:!bg-[#08090a] border-neutral-200 dark:border-neutral-800/80 text-neutral-900 dark:text-neutral-200 rounded-lg shadow-sm h-8 flex items-center justify-center px-3"
                glowColor="rgba(255, 255, 255, 0.2)"
                hoverTextColor="white"
              >
                <div className="flex gap-2 text-xs py-0.5 items-center">
                  <HomeIcon className="w-3 h-3" />
                  <p>Campaigns</p>
                </div>
              </HoverButton>
              <UserButton />
            </Show>
          </div>

          {/* <header className="flex justify-end items-center p-4 gap-4 h-16">
                     <Show when="signed-out">
                       <SignInButton />
                       <SignUpButton>
                         <button className="bg-purple-700 text-white rounded-full font-medium text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 cursor-pointer">
                           Sign Up
                         </button>
                       </SignUpButton>
                     </Show>
                     <Show when="signed-in">
                       <UserButton />
                     </Show>
                   </header> */}

          {/* Mobile Toggle */}
          <button
            className="md:hidden p-2 text-zinc-600 dark:text-zinc-400"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile Menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden bg-white dark:bg-zinc-950 border-b border-zinc-200 dark:border-zinc-800 overflow-hidden"
            >
              <div className="flex flex-col p-6 gap-4">
                {/* {NAV_LINKS.map((link) => (
                <Link
                  key={link.name}
                  href={link.href}
                  className="text-sm font-medium text-zinc-600 dark:text-zinc-400"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {link.name}
                </Link>
              ))} */}
                <hr className="border-zinc-200 dark:border-zinc-800" />
                <div className="flex flex-col gap-3">
                  <button className="w-full text-center py-2 text-sm font-medium border border-zinc-200 dark:border-zinc-800 rounded-lg">
                    Log in
                  </button>
                  <button className="w-full text-center py-2 text-sm font-medium bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 rounded-lg">
                    Sign up
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>
    </div>
  );
}
