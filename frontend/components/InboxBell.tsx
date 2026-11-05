"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Bell, BellRing } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useApi } from "@/lib/api";
import { type Inbox, inboxStore, useInbox } from "@/lib/inbox";
import { updatedLabel } from "@/types/campaign";

const POLL_MS = 60_000;
const chatHref = (campaignId: string, dealId: string) => `/campaign/${campaignId}/deals?chat=${dealId}`;

/** Checks for new replies every minute (and on focus), keeps the tab title's "(n)" and pops browser alerts
 * for new replies once the founder allows them. Mounted once, in the navbar. */
function usePoll() {
  const api = useApi();
  const seen = useRef<Set<string> | null>(null);
  const path = usePathname();
  const params = useSearchParams();
  const openChat = useRef<string | null>(null);
  openChat.current = path?.endsWith("/deals") ? params?.get("chat") ?? null : null;

  useEffect(() => {
    let alive = true;
    let busy = false;
    const base = document.title.replace(/^\(\d+\)\s*/, "");
    const tick = async () => {
      if (busy) return;
      busy = true;
      try {
        const box = (await api("/api/inbox")).data as Inbox;
        if (!alive) return;
        inboxStore.set(box);
        document.title = box.unread ? `(${box.unread}) ${base}` : base;
        const ids = box.items.filter((i) => i.event_id).map((i) => i.event_id as string);
        if (seen.current) {
          const fresh = box.items.filter((i) => i.event_id && !seen.current!.has(i.event_id));
          for (const i of fresh) {
            const looking = !document.hidden && openChat.current === i.deal_id;
            if (looking || typeof Notification === "undefined" || Notification.permission !== "granted") continue;
            const n = new Notification(`${i.name ?? "A creator"} replied`, { body: i.text ?? "", icon: i.avatar_url ?? undefined, tag: i.event_id ?? undefined });
            n.onclick = () => {
              window.focus();
              window.location.href = chatHref(i.campaign_id, i.deal_id);
            };
          }
        }
        seen.current = new Set([...(seen.current ?? []), ...ids]);
      } catch {
        // offline or signed out: try again next time
      } finally {
        busy = false;
      }
    };
    tick();
    const t = setInterval(tick, POLL_MS);
    const onFocus = () => tick();
    window.addEventListener("focus", onFocus);
    inboxStore.setRefresher(tick);
    return () => {
      alive = false;
      clearInterval(t);
      window.removeEventListener("focus", onFocus);
      inboxStore.setRefresher(null);
      document.title = base;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render; one poller for the session
  }, []);
}

/** The bell: new replies and drafts waiting, across all campaigns. */
export function InboxBell() {
  usePoll();
  const box = useInbox();
  const [open, setOpen] = useState(false);
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">("default");
  useEffect(() => {
    setPerm(typeof Notification === "undefined" ? "unsupported" : Notification.permission); // eslint-disable-line react-hooks/set-state-in-effect -- browser-only value
  }, []);
  const count = box.unread || box.waiting;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" aria-label={count ? `${count} waiting for you` : "Nothing new"}
          className="relative h-8 w-8 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors">
          <motion.span key={box.unread} initial={box.unread ? { rotate: -18 } : false} animate={{ rotate: 0 }} transition={{ type: "spring", stiffness: 400, damping: 8 }}>
            {box.unread ? <BellRing size={15} /> : <Bell size={15} />}
          </motion.span>
          <AnimatePresence>
            {count > 0 && (
              <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={{ type: "spring", stiffness: 500, damping: 25 }}
                className={`absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full text-[10px] font-medium flex items-center justify-center ${box.unread ? "bg-blue-500 text-white" : "bg-zinc-300 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100"}`}>
                {count > 9 ? "9+" : count}
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <div className="px-3 py-2.5 border-b border-zinc-200/70 dark:border-zinc-800/70 flex items-center justify-between">
          <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">Waiting for you</p>
          {perm === "default" && (
            <button type="button" onClick={() => Notification.requestPermission().then(setPerm)} className="text-[11px] text-blue-500 hover:underline">
              Turn on alerts
            </button>
          )}
          {perm === "denied" && <span className="text-[11px] text-zinc-500">Alerts blocked in browser</span>}
        </div>
        {box.items.length === 0 ? (
          <p className="px-3 py-8 text-center text-xs text-zinc-500">You&apos;re all caught up.</p>
        ) : (
          <ul className="max-h-[360px] overflow-y-auto p-1">
            {box.items.map((i) => (
              <li key={i.deal_id}>
                <Link href={chatHref(i.campaign_id, i.deal_id)} onClick={() => setOpen(false)}
                  className="flex items-start gap-2.5 px-2.5 py-2 rounded-md hover:bg-zinc-100 dark:hover:bg-[#17181a] transition-colors">
                  <CreatorAvatar name={i.name ?? "?"} src={i.avatar_url} className="w-7 h-7 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center shrink-0" textClassName="text-[11px] font-medium" />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <span className={`text-xs truncate ${i.unread ? "font-semibold text-zinc-900 dark:text-zinc-100" : "font-medium text-zinc-700 dark:text-zinc-300"}`}>{i.name}</span>
                      {i.unread > 0 && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />}
                      <span className="ml-auto text-[10px] text-zinc-400 shrink-0">{i.at ? updatedLabel(i.at) : ""}</span>
                    </span>
                    <span className="block text-[11px] text-zinc-500 truncate">{i.text ?? "ReachAI drafted a reply"}</span>
                    {i.campaign_name && <span className="block text-[10px] text-zinc-400 truncate">{i.campaign_name}</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
