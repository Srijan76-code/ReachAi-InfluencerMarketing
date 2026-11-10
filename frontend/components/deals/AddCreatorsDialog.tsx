"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Segmented } from "@/components/ui/segmented";
import { btn, btnPrimary, control } from "@/lib/ui";
import { Loader2 } from "lucide-react";
import type { Influencer } from "@/data/influencerList";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

/** Pick creators from this campaign (shortlist first) to talk to. Each gets a chat in Outreach and, unless you
 * untick it, ReachAI drafts a first message there for you to check and send. */
export function AddCreatorsDialog({ campaignId, api, existing, onAdded, trigger }: {
  campaignId: string;
  api: Api;
  existing: Set<string>;
  onAdded: (created: unknown[]) => void;
  trigger?: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [leads, setLeads] = useState<Influencer[]>([]);
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [view, setView] = useState<"shortlist" | "all">("shortlist");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState("");
  const [linkEmail, setLinkEmail] = useState("");
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState(true);

  // the chats are made right away; drafts land in them when they're written (a minute or two)
  const start = async (ids: string[]) => {
    if (draft) {
      await api(`/api/outreach/campaigns/${campaignId}/jobs`, { method: "POST", data: { selected_creator_ids: ids, collaboration_type: "sponsored_video", deliverables: [], auto_start: true } });
      return [];
    }
    const d = await api(`/api/campaigns/${campaignId}/deals`, { method: "POST", data: { creator_ids: ids } });
    return ((d.data as { created?: unknown[] })?.created) ?? [];
  };

  // a creator you already know: measured from their channel (no search needed), then added to deals
  const addByLink = async () => {
    setAdding(true);
    setError(null);
    try {
      const r = (await api(`/api/campaigns/${campaignId}/creators/by-link`, { method: "POST", data: { link, email: linkEmail || null } })).data as { lead: { id: string } };
      onAdded(await start([r.lead.id]));
      setLink("");
      setLinkEmail("");
      setOpen(false);
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Couldn't add that creator. Check the link and try again.");
    } finally {
      setAdding(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    setPicked(new Set());
    setError(null);
    Promise.all([api(`/api/campaigns/${campaignId}/leads`), api(`/api/saved?campaign_id=${campaignId}`)])
      .then(([l, s]) => {
        const result = (l.data as { result?: Influencer[] })?.result;
        setLeads(Array.isArray(result) ? result : []);
        const ids = new Set<string>();
        for (const item of (Array.isArray(s.data) ? s.data : []) as { lead_data?: { id?: string }; lead_id?: string }[]) {
          const id = item.lead_data?.id || item.lead_id;
          if (id) ids.add(id);
        }
        setSaved(ids);
        setView(ids.size ? "shortlist" : "all");
      })
      .catch(() => setError("Couldn't load your creators."));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [open, campaignId]);

  const shown = useMemo(
    () => leads.filter((l) => !existing.has(l.id) && (view === "all" || saved.has(l.id))),
    [leads, existing, view, saved],
  );

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      onAdded(await start([...picked]));
      setOpen(false);
    } catch {
      setError("Couldn't add them. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <button type="button" className={btnPrimary}>
            <Plus size={13} /> Add creators
          </button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md gap-4 bg-white dark:bg-[#0c0d0e]">
        <DialogHeader className="space-y-1">
          <DialogTitle className="text-[14px] font-medium">Add creators</DialogTitle>
          <DialogDescription className="text-xs">Each gets a chat here. Pick from your shortlist, or add one by link.</DialogDescription>
        </DialogHeader>
        <Segmented
          label="Which creators"
          size="sm"
          value={view}
          onChange={setView}
          options={[
            { value: "shortlist", label: "Shortlist", count: leads.filter((l) => saved.has(l.id) && !existing.has(l.id)).length },
            { value: "all", label: "All", count: leads.filter((l) => !existing.has(l.id)).length },
          ]}
        />
        <ul className="max-h-72 overflow-y-auto -mx-1 space-y-0.5">
          {shown.length === 0 ? (
            <li className="px-1 py-6 text-center text-xs text-zinc-500">
              {view === "shortlist" ? "Everyone on your shortlist already has a chat, or the shortlist is empty." : "Everyone already has a chat."}
            </li>
          ) : (
            shown.map((l) => (
              <li key={l.id}>
                <label className="flex items-center gap-2.5 px-1 py-1.5 rounded-md hover:bg-zinc-50 dark:hover:bg-zinc-900">
                  <input
                    type="checkbox"
                    checked={picked.has(l.id)}
                    onChange={() => setPicked((p) => { const n = new Set(p); if (n.has(l.id)) n.delete(l.id); else n.add(l.id); return n; })}
                    className="accent-zinc-900 dark:accent-zinc-100"
                  />
                  <CreatorAvatar name={l.title} src={l.avatar_url} className="w-7 h-7 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center shrink-0" textClassName="text-[11px] font-medium" />
                  <span className="text-[13px] text-zinc-900 dark:text-zinc-100 truncate flex-1">{l.title}</span>
                  <span className="text-[11px] text-zinc-500 font-mono">{Math.round(l.final_score ?? 0)}</span>
                </label>
              </li>
            ))
          )}
        </ul>
        <div className="space-y-2 border-t border-zinc-200/70 dark:border-zinc-800/70 pt-3">
          <p className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Or add by channel link</p>
          <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="youtube.com/@name or channel link" aria-label="Channel link" className={control} />
          <div className="flex gap-2">
            <input value={linkEmail} onChange={(e) => setLinkEmail(e.target.value.trim())} placeholder="Their email (optional)" aria-label="Their email" className={control} />
            <button type="button" onClick={addByLink} disabled={adding || !link.trim()} className={btn}>
              {adding && <Loader2 size={13} className="animate-spin" />} {adding ? "Adding" : "Add"}
            </button>
          </div>
        </div>
        {error && <p className="text-xs text-rose-500">{error}</p>}
        <div className="flex items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-xs text-zinc-700 dark:text-zinc-300">
            <input type="checkbox" checked={draft} onChange={(e) => setDraft(e.target.checked)} className="accent-zinc-900 dark:accent-zinc-100" />
            Draft a first message for each
          </label>
          <button type="button" onClick={add} disabled={busy || !picked.size} className={btnPrimary}>
            {busy ? "Adding…" : `Add ${picked.size || ""}`}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
