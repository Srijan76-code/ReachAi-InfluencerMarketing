"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Coins, KeyRound, Loader2, Menu, Plus, X } from "lucide-react";
import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { useCreateCampaign } from "@/lib/useCreateCampaign";
import { plural, useCredits } from "@/lib/credits";
import { usagePanel } from "@/lib/usage";
import { InboxBell } from "./InboxBell";
import { OnboardAgent } from "./OnboardAgent";
import { UsageSheet } from "./billing/UsageSheet";

/** Left: where you go. Right: what you do. One style per group. */
const LINKS = [
  { name: "Campaigns", href: "/campaign", signedIn: true },
  { name: "Pricing", href: "/pricing", signedIn: false },
  { name: "Docs", href: "/docs", signedIn: false },
];

const DEFAULT_ORIGIN = "https://reach-ai-influencer-marketing.vercel.app";

function NavLink({ href, name, onClick }: { href: string; name: string; onClick?: () => void }) {
  const path = usePathname();
  const active = path === href || (href !== "/" && path?.startsWith(href));
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "text-[13px] transition-colors",
        active ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100",
      )}
    >
      {name}
    </Link>
  );
}

function AccountMenu() {
  const credits = useCredits();
  const summary = credits ? `${plural(credits.balance)} · ${credits.plan[0].toUpperCase()}${credits.plan.slice(1)}` : "Credits";
  return (
    <UserButton>
      <UserButton.MenuItems>
        <UserButton.Action label={summary} labelIcon={<Coins className="w-4 h-4" />} onClick={() => usagePanel.open()} />
        <UserButton.Action label="Billing and usage" labelIcon={<Coins className="w-4 h-4" />} onClick={() => usagePanel.open()} />
        <UserButton.Link label="API keys" labelIcon={<KeyRound className="w-4 h-4" />} href="/agents" />
        <UserButton.Action label="manageAccount" />
        <UserButton.Action label="signOut" />
      </UserButton.MenuItems>
    </UserButton>
  );
}

export default function Header() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [origin, setOrigin] = useState(DEFAULT_ORIGIN);
  const { create: createCampaign, creating } = useCreateCampaign();

  useEffect(() => setOrigin(window.location.origin), []);
  useEffect(() => setMobileOpen(false), [pathname]);

  // The docs have their own navigation bar.
  if (pathname?.startsWith("/docs")) return null;

  return (
    <div className="fixed top-0 inset-x-0 z-50 bg-zinc-50/90 dark:bg-[#08090a]/90 backdrop-blur">
      <nav className="max-w-7xl mx-auto h-14 px-4 sm:px-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-7">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-7 h-7 bg-zinc-900 dark:bg-neutral-300 rounded-lg flex items-center justify-center group-hover:rotate-6 transition-transform">
              <div className="w-3 h-3 bg-white dark:bg-zinc-900 rounded-sm" />
            </div>
            <span className="font-bold text-sm tracking-tighter text-zinc-900 dark:text-zinc-100">ReachAI</span>
          </Link>
          <div className="hidden md:flex items-center gap-6">
            {LINKS.map((l) =>
              l.signedIn ? (
                <Show key={l.href} when="signed-in">
                  <NavLink {...l} />
                </Show>
              ) : (
                <NavLink key={l.href} {...l} />
              ),
            )}
          </div>
        </div>

        <div className="hidden md:flex items-center gap-2.5">
          <Show when="signed-out">
            <SignInButton>
              <button className="h-8 px-3 text-[13px] text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                Log in
              </button>
            </SignInButton>
            <SignUpButton>
              <button className="group h-8 px-3 text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-300 dark:text-zinc-900 rounded-lg flex items-center gap-1.5 hover:opacity-90 transition-opacity">
                Sign up
                <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
            </SignUpButton>
          </Show>
          <Show when="signed-in">
            <OnboardAgent origin={origin} compact />
            <button
              type="button"
              onClick={createCampaign}
              disabled={creating}
              className="h-8 px-3 text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-300 dark:text-zinc-900 rounded-lg flex items-center gap-1.5 hover:opacity-90 transition-opacity disabled:opacity-60"
            >
              {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              New campaign
            </button>
            <Suspense fallback={null}>
              <InboxBell />
            </Suspense>
            <AccountMenu />
            <UsageSheet />
          </Show>
        </div>

        <button
          type="button"
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          className="md:hidden p-2 text-zinc-600 dark:text-zinc-400"
          onClick={() => setMobileOpen((o) => !o)}
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-b border-zinc-200 dark:border-zinc-800 overflow-hidden"
          >
            <div className="flex flex-col p-4 gap-4">
              <Show when="signed-in">
                <NavLink href="/campaign" name="Campaigns" />
              </Show>
              <NavLink href="/pricing" name="Pricing" />
              <NavLink href="/docs" name="Docs" />
              <Show when="signed-in">
                <button
                  type="button"
                  onClick={() => {
                    setMobileOpen(false);
                    usagePanel.open();
                  }}
                  className="text-left text-[13px] text-zinc-500"
                >
                  Billing and usage
                </button>
                <NavLink href="/agents" name="API keys" />
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setMobileOpen(false);
                      createCampaign();
                    }}
                    className="h-8 px-3 text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-300 dark:text-zinc-900 rounded-lg flex items-center gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    New campaign
                  </button>
                  <OnboardAgent origin={origin} compact />
                </div>
              </Show>
              <Show when="signed-out">
                <div className="flex gap-2">
                  <SignInButton>
                    <button className="flex-1 h-9 text-[13px] border border-zinc-200 dark:border-zinc-800 rounded-lg">Log in</button>
                  </SignInButton>
                  <SignUpButton>
                    <button className="flex-1 h-9 text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-300 dark:text-zinc-900 rounded-lg">
                      Sign up
                    </button>
                  </SignUpButton>
                </div>
              </Show>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
