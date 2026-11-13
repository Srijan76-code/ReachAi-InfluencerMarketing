"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Coins, KeyRound, Loader2, Menu, PlusCircle, X } from "lucide-react";
import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { useCreateCampaign } from "@/lib/useCreateCampaign";
import { creditsStore, plural, useCredits } from "@/lib/credits";
import { useApi } from "@/lib/api";
import { usagePanel } from "@/lib/usage";
import { InboxBell } from "./InboxBell";
import { OnboardAgent } from "./OnboardAgent";
import { UsageSheet } from "./billing/UsageSheet";
import { HoverButton } from "./buttons/HoverButton";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

const DEFAULT_ORIGIN = "https://reach-ai-influencer-marketing.vercel.app";

type NavItem = { name: string; href: string };

/** Links with a soft pill that slides to whichever one the mouse is on (and rests on the current page). */
export function NavGroup({ items, id, strong = false }: { items: NavItem[]; id: string; strong?: boolean }) {
  const path = usePathname();
  const [hovered, setHovered] = useState<string | null>(null);
  const active = items.find((i) => path === i.href || path?.startsWith(`${i.href}/`))?.href ?? null;
  const pill = hovered ?? active;
  return (
    <div className="flex items-center" onMouseLeave={() => setHovered(null)}>
      {items.map((i) => (
        <Link
          key={i.href}
          href={i.href}
          onMouseEnter={() => setHovered(i.href)}
          className={cn(
            "relative px-3 h-8 flex items-center text-[13px] transition-colors",
            strong ? "font-medium" : "",
            active === i.href || hovered === i.href
              ? "text-zinc-900 dark:text-zinc-100"
              : strong
                ? "text-zinc-600 dark:text-zinc-300"
                : "text-zinc-500 dark:text-zinc-500",
          )}
        >
          {pill === i.href && (
            <motion.span
              layoutId={`nav-pill-${id}`}
              className="absolute inset-0 rounded-lg bg-zinc-200/70 dark:bg-zinc-800/70"
              transition={{ type: "spring", stiffness: 500, damping: 38 }}
            />
          )}
          <span className="relative">{i.name}</span>
        </Link>
      ))}
    </div>
  );
}

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

/** Credits, alerts and account in one capsule: everything about "you" reads as one object. */
/** If this person arrived through an invite link, claim it once their account exists. */
function useClaimInvite() {
  const api = useApi();
  useEffect(() => {
    let code: string | null = null;
    try {
      code = localStorage.getItem("reachai_ref");
    } catch {
      return;
    }
    if (!code) return;
    api("/api/billing/referral", { method: "POST", data: { code } })
      .then(() => creditsStore.refresh())
      .catch(() => undefined) // invalid, own or old invite: nothing to do
      .finally(() => {
        try {
          localStorage.removeItem("reachai_ref");
        } catch {
          // ignore
        }
      });
  }, [api]);
}

function AccountCapsule() {
  useClaimInvite();
  const credits = useCredits();
  const low = credits ? credits.balance <= 1 : false;
  return (
    <div className="flex items-center h-9 pl-1 pr-1 gap-0.5 rounded-full border border-zinc-200 dark:border-zinc-800 bg-white/60 dark:bg-[#0c0d0e]">
      <button
        type="button"
        onClick={() => usagePanel.open()}
        title="Billing and usage"
        className={cn(
          "h-7 pl-2 pr-2.5 rounded-full flex items-center gap-1.5 text-xs transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-900",
          low ? "text-amber-600 dark:text-amber-400" : "text-zinc-700 dark:text-zinc-300",
        )}
      >
        <Coins className="w-3.5 h-3.5" />
        <span className="font-mono tabular-nums">{credits ? credits.balance : "–"}</span>
        <span className="text-zinc-500">credits</span>
      </button>
      <span className="w-px h-4 bg-zinc-200 dark:bg-zinc-800" />
      <Suspense fallback={null}>
        <InboxBell />
      </Suspense>
      <span className="w-px h-4 bg-zinc-200 dark:bg-zinc-800" />
      <span className="h-7 w-7 grid place-items-center">
        <AccountMenu />
      </span>
    </div>
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
        <div className="flex items-center gap-5">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-7 h-7 bg-zinc-900 dark:bg-neutral-300 rounded-lg flex items-center justify-center group-hover:rotate-6 transition-transform">
              <div className="w-3 h-3 bg-white dark:bg-zinc-900 rounded-sm" />
            </div>
            <span className="font-bold text-sm tracking-tighter text-zinc-900 dark:text-zinc-100">ReachAI</span>
          </Link>
          <Show when="signed-in">
            <div className="hidden md:block">
              <NavGroup id="main" strong items={[{ name: "Campaigns", href: "/campaign" }]} />
            </div>
          </Show>
        </div>

        <div className="hidden md:flex items-center gap-3">
          <NavGroup id="help" items={[{ name: "Pricing", href: "/pricing" }, { name: "Docs", href: "/docs" }]} />
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
            <span className="w-px h-5 bg-zinc-200 dark:bg-zinc-800" />
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <OnboardAgent origin={origin} compact />
                </span>
              </TooltipTrigger>
              <TooltipContent side="bottom">Connect your agent: copies a setup line to paste into it</TooltipContent>
            </Tooltip>
            <HoverButton
              onClick={createCampaign}
              disabled={creating}
              className="!bg-zinc-50 dark:!bg-[#08090a] !border-neutral-200 dark:!border-neutral-800/80 rounded-lg shadow-sm h-8 flex items-center justify-center px-3 disabled:opacity-60"
              glowColor="var(--hover-btn-glow)"
              textColor="var(--hover-btn-text)"
              hoverTextColor="var(--hover-btn-text-hover)"
            >
              <span className="relative flex gap-2 text-xs py-0.5 items-center">
                {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlusCircle className="w-3 h-3" />}
                {creating ? "Creating…" : "New campaign"}
              </span>
            </HoverButton>
            <AccountCapsule />
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
                    <PlusCircle className="w-3.5 h-3.5" />
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
