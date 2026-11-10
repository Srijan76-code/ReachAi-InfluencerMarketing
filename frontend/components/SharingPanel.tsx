"use client";

import { useCallback, useEffect, useState } from "react";
import { Bookmark, Eye, Handshake, MessageSquare, Share2, ThumbsDown, ThumbsUp } from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Segmented } from "@/components/ui/segmented";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { ShareManager, type ShareScope } from "@/components/ShareManager";
import { updatedLabel } from "@/types/campaign";

/** The sharing command centre (roadmap F1.18c): who has access (People), what happened (Activity) and what
 *  people said about each creator (By creator), in one side panel next to the list. */

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

type Person = {
  link_id: string; kind: "person" | "anyone"; email: string | null; role: string; view_count: number;
  last_viewed_at: string | null; creators: number; reviewed: number; yes: number; no: number;
};
type Event = {
  type: "opened" | "feedback"; by: string; creator_id?: string; name?: string; avatar_url?: string | null;
  verdict: "yes" | "no" | null; comment: string | null; at: string | null;
};
type CreatorRow = {
  creator_id: string; name: string; avatar_url: string | null; yes: number; no: number;
  notes: { by: string; verdict: "yes" | "no" | null; comment: string | null; at: string | null }[];
};
export type Activity = { people: Person[]; events: Event[]; by_creator: CreatorRow[]; latest_at: string | null };

const seenKey = (id: string) => `reachai:share-seen:${id}`;
function readSeen(id: string) {
  try {
    return window.localStorage.getItem(seenKey(id));
  } catch {
    return null;
  }
}

type Tab = "people" | "activity" | "creators";

export function SharingPanel({ campaignId, api, scopes, savedIds, onOpenCreator, onShortlist, onAddToDeals }: {
  campaignId: string;
  api: Api;
  scopes: ShareScope[];
  savedIds: Set<string>;
  onOpenCreator: (creatorId: string) => void;
  onShortlist: (creatorIds: string[]) => Promise<void> | void;
  onAddToDeals: (creatorIds: string[]) => Promise<number>;
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("people");
  const [activity, setActivity] = useState<Activity | null>(null);
  const [seen, setSeen] = useState<string | null>(null);
  const [onlyComments, setOnlyComments] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(
    () => api(`/api/campaigns/${campaignId}/share-activity`).then((r) => setActivity(r.data as Activity)).catch(() => {}),
    [api, campaignId],
  );

  // load once for the dot; again whenever the panel opens
  useEffect(() => {
    setSeen(readSeen(campaignId));
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [campaignId]);
  useEffect(() => {
    if (!open) return;
    load();
    setNotice(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [open]);

  // opening Activity or By creator marks everything as seen
  useEffect(() => {
    if (!open || tab === "people" || !activity?.latest_at) return;
    try {
      window.localStorage.setItem(seenKey(campaignId), activity.latest_at);
    } catch {}
    setSeen(activity.latest_at);
  }, [open, tab, activity?.latest_at, campaignId]);

  const unseen = activity?.events.filter((e) => e.at && (!seen || e.at > seen)).length ?? 0;
  const approved = (activity?.by_creator ?? []).filter((c) => c.yes > c.no).map((c) => c.creator_id);
  const rows = (activity?.by_creator ?? []).filter((c) => !onlyComments || c.notes.some((n) => n.comment));

  const openCreator = (id?: string) => {
    if (!id) return;
    setOpen(false);
    onOpenCreator(id);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="relative flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors"
        aria-label={unseen ? `Share, ${unseen} new` : "Share"}
      >
        <Share2 size={14} />
        Share
        {unseen > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 rounded-full bg-blue-500 text-white text-[10px] font-semibold leading-4 text-center" title={`${unseen} new since you last looked`}>
            {unseen > 9 ? "9+" : unseen}
          </span>
        )}
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="sm:max-w-[480px] bg-white dark:bg-[#0c0d0e] border-l border-zinc-200/80 dark:border-zinc-800/80 p-0 flex flex-col h-full">
          <div className="p-5 pb-4 border-b border-zinc-200/60 dark:border-zinc-800/60 space-y-3">
            <div>
              <SheetTitle className="text-base">Sharing</SheetTitle>
              <SheetDescription className="text-xs">No account needed · contact details are never shared</SheetDescription>
            </div>
            <Segmented
              label="Sharing"
              size="sm"
              value={tab}
              onChange={setTab}
              options={[
                { value: "people", label: "People", count: activity?.people.length },
                { value: "activity", label: unseen ? `Activity · ${unseen} new` : "Activity" },
                { value: "creators", label: "By creator", count: activity?.by_creator.length },
              ]}
            />
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {tab === "people" && (
              <ShareManager campaignId={campaignId} api={api} scopes={scopes} active={open && tab === "people"} onChanged={load} />
            )}

            {tab === "activity" && (
              !activity?.events.length ? (
                <p className="text-xs text-zinc-500 py-8 text-center">Nothing yet. When people open your link or react to creators, it shows up here.</p>
              ) : (
                <ol className="space-y-1">
                  {activity.events.map((e, i) => {
                    const isNew = e.at && (!seen || e.at > seen);
                    return (
                      <li key={i} className="flex gap-3 py-2 border-b border-zinc-100 dark:border-zinc-900 last:border-0">
                        <span className="mt-0.5 h-6 w-6 shrink-0 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center">
                          {e.type === "opened" ? <Eye size={12} className="text-zinc-500" /> : e.verdict === "yes" ? <ThumbsUp size={12} className="text-emerald-500" /> : e.verdict === "no" ? <ThumbsDown size={12} className="text-rose-500" /> : <MessageSquare size={12} className="text-zinc-500" />}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] text-zinc-800 dark:text-zinc-200">
                            <span className="font-medium">{e.by}</span>{" "}
                            {e.type === "opened" ? (
                              "opened the shortlist"
                            ) : (
                              <>
                                {e.verdict === "yes" ? "approved" : e.verdict === "no" ? "rejected" : "commented on"}{" "}
                                <button type="button" onClick={() => openCreator(e.creator_id)} className="font-medium hover:underline underline-offset-2">{e.name}</button>
                              </>
                            )}
                          </p>
                          {e.comment && <p className="text-xs text-zinc-500 mt-0.5">“{e.comment}”</p>}
                        </div>
                        <span className="text-[11px] text-zinc-500 shrink-0 flex items-center gap-1.5">
                          {isNew && <span className="h-1.5 w-1.5 rounded-full bg-blue-500" aria-label="new" />}
                          {e.at ? updatedLabel(e.at) : ""}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              )
            )}

            {tab === "creators" && (
              !activity?.by_creator.length ? (
                <p className="text-xs text-zinc-500 py-8 text-center">No feedback yet. Invite someone who <span className="font-medium">Can review</span> from the People tab.</p>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      disabled={!approved.filter((id) => !savedIds.has(id)).length}
                      onClick={async () => {
                        const todo = approved.filter((id) => !savedIds.has(id));
                        await onShortlist(todo);
                        setNotice(`${todo.length} added to your shortlist`);
                      }}
                      className="h-8 px-3 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40 flex items-center gap-1.5"
                    >
                      <Bookmark size={12} /> Shortlist approved ({approved.filter((id) => !savedIds.has(id)).length})
                    </button>
                    <button
                      type="button"
                      disabled={!approved.length}
                      onClick={async () => {
                        const added = await onAddToDeals(approved);
                        setNotice(added ? `${added} added to Outreach` : "They're already in Outreach");
                      }}
                      className="h-8 px-3 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-40 flex items-center gap-1.5"
                    >
                      <Handshake size={12} /> Add approved to outreach ({approved.length})
                    </button>
                    <label className="ml-auto flex items-center gap-1.5 text-[11px] text-zinc-500">
                      <input type="checkbox" checked={onlyComments} onChange={(e) => setOnlyComments(e.target.checked)} className="accent-zinc-900 dark:accent-zinc-100" />
                      With comments
                    </label>
                  </div>
                  {notice && <p className="text-[11px] text-emerald-600 dark:text-emerald-400">{notice}</p>}
                  <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
                    {rows.map((c) => (
                      <li key={c.creator_id} className="py-2.5">
                        <div className="flex items-center gap-2.5">
                          <CreatorAvatar name={c.name} src={c.avatar_url} className="w-7 h-7 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center shrink-0" textClassName="text-[11px] font-medium" />
                          <button type="button" onClick={() => openCreator(c.creator_id)} className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100 truncate hover:underline underline-offset-2 text-left flex-1">
                            {c.name}
                          </button>
                          <span className="flex items-center gap-2 text-xs font-mono shrink-0">
                            <span className={`flex items-center gap-0.5 ${c.yes ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-400"}`}><ThumbsUp size={11} />{c.yes}</span>
                            <span className={`flex items-center gap-0.5 ${c.no ? "text-rose-500" : "text-zinc-400"}`}><ThumbsDown size={11} />{c.no}</span>
                          </span>
                        </div>
                        {c.notes.some((n) => n.comment) && (
                          <ul className="mt-1.5 ml-9 space-y-1">
                            {c.notes.filter((n) => n.comment).map((n, i) => (
                              <li key={i} className="text-xs text-zinc-600 dark:text-zinc-400">
                                <span className="font-medium text-zinc-700 dark:text-zinc-300">{n.by}:</span> “{n.comment}”
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            )}
          </div>

          {/* People summary under the tabs: who opened, who reviewed */}
          {tab !== "people" && activity && activity.people.length > 0 && (
            <div className="border-t border-zinc-200/60 dark:border-zinc-800/60 p-4 space-y-1.5">
              {activity.people.map((p) => (
                <p key={p.link_id} className="text-[11px] text-zinc-500 flex justify-between gap-2">
                  <span className="truncate text-zinc-700 dark:text-zinc-300">{p.email ?? "Anyone with the link"}</span>
                  <span className="shrink-0">
                    {p.view_count ? `opened ${updatedLabel(p.last_viewed_at || "")}` : "not opened yet"}
                    {p.role === "reviewer" ? ` · reviewed ${p.reviewed}/${p.creators}` : ""}
                  </span>
                </p>
              ))}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
