"use client";

import { useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { Segmented } from "@/components/ui/segmented";
import { btnPrimary } from "@/lib/ui";
import type { Influencer } from "@/data/influencerList";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

/** Pick creators from this campaign (shortlist first) to start deals with. */
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
      const r = await api(`/api/campaigns/${campaignId}/deals`, { method: "POST", data: { creator_ids: [...picked] } });
      onAdded(((r.data as { created?: unknown[] })?.created) ?? []);
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
          <DialogTitle className="text-[14px] font-medium">Add creators to deals</DialogTitle>
          <DialogDescription className="text-xs">Pick who you&apos;re talking to. They start in Contacted.</DialogDescription>
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
              {view === "shortlist" ? "Everyone on your shortlist is already in deals, or the shortlist is empty." : "Everyone is already in deals."}
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
        {error && <p className="text-xs text-rose-500">{error}</p>}
        <div className="flex justify-end">
          <button type="button" onClick={add} disabled={busy || !picked.size} className={btnPrimary}>
            {busy ? "Adding…" : `Add ${picked.size || ""} to deals`}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
