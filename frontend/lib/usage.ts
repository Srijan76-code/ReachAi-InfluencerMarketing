"use client";

import { useSyncExternalStore } from "react";

/** Whether the "Billing & usage" side panel is open (opened from the avatar menu or anywhere else). */
let open = false;
const listeners = new Set<() => void>();

export const usagePanel = {
  open() {
    open = true;
    listeners.forEach((l) => l());
  },
  close() {
    open = false;
    listeners.forEach((l) => l());
  },
};

export function useUsagePanel(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => open,
    () => false,
  );
}
