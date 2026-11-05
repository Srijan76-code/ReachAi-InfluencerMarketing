"use client";

import type { CSSProperties } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

/** Text with a light sweeping across it, for "ReachAI is drafting…" (adapted from Vercel AI Elements' Shimmer). */
export function Shimmer({ children, className, duration = 1.8 }: { children: string; className?: string; duration?: number }) {
  return (
    <motion.span
      initial={{ backgroundPosition: "100% center" }}
      animate={{ backgroundPosition: "0% center" }}
      transition={{ duration, ease: "linear", repeat: Infinity }}
      className={cn(
        "relative inline-block bg-[length:250%_100%,auto] bg-clip-text text-transparent [background-repeat:no-repeat,padding-box]",
        "[--shine:#fff] dark:[--shine:#0c0d0e] [--base:#71717a] dark:[--base:#a1a1aa]",
        className,
      )}
      style={{
        "--spread": `${children.length * 2}px`,
        backgroundImage: "linear-gradient(90deg,#0000 calc(50% - var(--spread)),var(--shine),#0000 calc(50% + var(--spread))), linear-gradient(var(--base),var(--base))",
      } as CSSProperties}
    >
      {children}
    </motion.span>
  );
}

/** Three dots that bounce, like someone typing. */
export function TypingDots({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1", className)} aria-label="Writing">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-zinc-400 dark:bg-zinc-500"
          animate={{ y: [0, -4, 0], opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
        />
      ))}
    </span>
  );
}
