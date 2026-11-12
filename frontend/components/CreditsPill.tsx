"use client";

import Link from "next/link";
import NumberFlow from "@number-flow/react";
import { Coins } from "lucide-react";
import { useCredits } from "@/lib/credits";

/** Credits left, in the navbar. Opens the billing page. */
export function CreditsPill() {
  const credits = useCredits();
  if (!credits) return null;
  const low = credits.balance <= 1;
  return (
    <Link
      href="/billing"
      title="Credits: only creator searches use them"
      className={`flex items-center gap-1.5 h-8 px-2.5 rounded-lg border text-xs transition-colors ${
        low
          ? "border-amber-300/60 text-amber-700 dark:border-amber-500/30 dark:text-amber-400"
          : "border-neutral-200 dark:border-neutral-800/80 text-neutral-700 dark:text-neutral-300 hover:text-neutral-900 dark:hover:text-neutral-100"
      }`}
    >
      <Coins className="w-3 h-3" />
      <NumberFlow value={credits.balance} className="font-mono tabular-nums" />
      <span className="text-neutral-500">credits</span>
    </Link>
  );
}
