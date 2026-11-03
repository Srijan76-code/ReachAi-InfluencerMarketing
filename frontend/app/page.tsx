import Link from "next/link";
import { ArrowRight, BookOpen, PlayCircle } from "lucide-react";
import { Show, SignInButton, SignUpButton } from "@clerk/nextjs";

// Temporary landing page until the full marketing site is ready.
export default function Home() {
  return (
    <main className="min-h-screen flex items-center justify-center px-6 pt-14">
      <div className="w-full max-w-xl flex flex-col items-center text-center gap-8">
        <span className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] px-3 py-1 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          ReachAI
        </span>

        <div className="flex flex-col gap-4">
          <h1 className="text-5xl sm:text-6xl font-semibold tracking-tighter text-zinc-900 dark:text-zinc-100">
            Coming soon
          </h1>
          <p className="text-[15px] leading-relaxed text-zinc-500 dark:text-zinc-400 text-balance">
            Creator marketing for founders. Find the creators who will actually convert for your product,
            see what each one should cost, and reach them from one place.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Show when="signed-out">
            <SignUpButton>
              <button className="group text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-5 py-2 rounded-full flex items-center gap-1.5 hover:opacity-90 transition-all shadow-sm">
                Get early access
                <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
            </SignUpButton>
            <SignInButton>
              <button className="text-[13px] font-medium text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] px-5 py-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-all">
                Log in
              </button>
            </SignInButton>
          </Show>
          <Show when="signed-in">
            <Link
              href="/campaign"
              className="group text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-5 py-2 rounded-full flex items-center gap-1.5 hover:opacity-90 transition-all shadow-sm"
            >
              Go to your campaigns
              <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </Show>
        </div>

        <div className="flex items-center gap-6 text-[13px]">
          <Link
            href="/demo"
            className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
          >
            <PlayCircle size={14} />
            See a demo campaign
          </Link>
          <span className="w-px h-4 bg-zinc-200 dark:bg-zinc-800" />
          <Link
            href="/docs"
            className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
          >
            <BookOpen size={14} />
            Read the docs
          </Link>
        </div>
      </div>
    </main>
  );
}
