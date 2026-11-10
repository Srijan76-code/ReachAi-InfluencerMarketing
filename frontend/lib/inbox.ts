"use client";

import { useSyncExternalStore } from "react";

/** Replies waiting across all campaigns (backend GET /api/inbox): the bell, tab badges and browser alerts. */
export type InboxItem = {
  campaign_id: string;
  campaign_name: string | null;
  deal_id: string;
  name: string | null;
  avatar_url: string | null;
  unread: number;
  text: string | null;
  at: string | null;
  event_id: string | null;
  draft: boolean;
};
export type Inbox = { items: InboxItem[]; unread: number; waiting: number; by_campaign: Record<string, { unread: number; waiting: number }> };

const EMPTY: Inbox = { items: [], unread: 0, waiting: 0, by_campaign: {} };
let state: Inbox = EMPTY;
const listeners = new Set<() => void>();
let refresher: (() => void) | null = null;

export const inboxStore = {
  set(next: Inbox) {
    state = next;
    listeners.forEach((l) => l());
  },
  /** A chat was opened: its replies are read (until the next poll confirms it). */
  markRead(dealId: string) {
    const items = state.items.map((i) => (i.deal_id === dealId ? { ...i, unread: 0 } : i)).filter((i) => i.unread || i.draft);
    const by: Inbox["by_campaign"] = {};
    for (const i of items) {
      const b = (by[i.campaign_id] ??= { unread: 0, waiting: 0 });
      b.unread += i.unread;
      b.waiting += 1;
    }
    inboxStore.set({ items, unread: items.reduce((n, i) => n + i.unread, 0), waiting: items.length, by_campaign: by });
  },
  setRefresher(fn: (() => void) | null) {
    refresher = fn;
  },
  /** Ask the poller to check now (after sending, pasting, approving). */
  refresh() {
    refresher?.();
  },
};

export function useInbox(): Inbox {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
    () => EMPTY,
  );
}
