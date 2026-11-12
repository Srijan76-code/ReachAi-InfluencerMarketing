"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { useApi } from "@/lib/api";

/** The signed-in user's credits (backend GET /api/billing/balance), shared by the header and the billing page. */
export type Credits = {
  plan: string;
  balance: number;
  buckets: { monthly: number; rollover: number; bonus: number; pack: number };
  held: number;
  monthly_credits: number;
  resets_at: string;
  search_credits: Record<string, number>;
};

export type Quote = { credits: number; platforms: string[]; find_more: boolean; balance: number; enough: boolean };

/** What the backend says when a search can't start (402 / 429). */
export type CreditError = { code: "not_enough_credits" | "daily_limit"; message: string; needed?: number; balance?: number };

let state: Credits | null = null;
const listeners = new Set<() => void>();
let loader: (() => Promise<void>) | null = null;

export const creditsStore = {
  set(next: Credits | null) {
    state = next;
    listeners.forEach((l) => l());
  },
  /** Re-read the balance (after a search starts or finishes). */
  refresh() {
    void loader?.();
  },
};

export function useCredits(): Credits | null {
  const api = useApi();
  const load = useCallback(async () => {
    try {
      creditsStore.set((await api("/api/billing/balance")).data as Credits);
    } catch {
      // Not signed in yet or offline: keep what we have.
    }
  }, [api]);

  useEffect(() => {
    loader = load;
    if (!state) void load();
    const onFocus = () => void load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
    () => null,
  );
}

export const plural = (n: number, word = "credit") => `${n} ${word}${n === 1 ? "" : "s"}`;

export const resetLabel = (iso?: string) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";

/** Turn an error from a search start into words, or null if it isn't about credits. */
export function creditErrorText(detail: unknown): string | null {
  const d = detail as CreditError | undefined;
  if (!d || typeof d !== "object" || !("code" in d)) return null;
  if (d.code === "not_enough_credits") return `${d.message} Credits reset each month.`;
  return d.message;
}
