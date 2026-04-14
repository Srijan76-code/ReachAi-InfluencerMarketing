"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Github, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils"; // standard shadcn helper
import { Skiper26 } from "./ui/skiper-ui/skiper26";

const NAV_LINKS = [
  { name: "Features", href: "#features" },
  { name: "Solutions", href: "#solutions" },
  { name: "Resources", href: "#resources" },
  { name: "Pricing", href: "#pricing" },
];

export default function Header() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={cn(
        "fixed top-0 inset-x-0 z-50 h-12 transition-all duration-300  bg-zinc-50 dark:bg-[#08090a]",
        isScrolled 
          ? "py-3 backdrop-blur-md border-zinc-200 dark:border-zinc-800" 
          : "py-5 bg-transparent border-transparent"
      )}
    >
      <div className="max-w-7xl mx-auto h-full px-6 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 group">
          <div className="w-7 h-7 bg-zinc-900 dark:bg-white rounded-lg flex items-center justify-center group-hover:rotate-6 transition-transform">
            <div className="w-3 h-3 bg-white dark:bg-zinc-900 rounded-sm" />
          </div>
          <span className="font-bold text-sm tracking-tighter text-zinc-900 dark:text-zinc-100">
            ReachAI
          </span>
        </Link>

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
          <Link
            href="/login"
            className="text-[13px] font-medium text-zinc-600 dark:text-zinc-400 px-4 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-full transition-all"
          >
            Log in
          </Link>
          <Link
            href="/signup"
            className="group text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-4 py-1.5 rounded-full flex items-center gap-1.5 hover:opacity-90 transition-all shadow-sm"
          >
            Sign up
            <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>

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
  );
}