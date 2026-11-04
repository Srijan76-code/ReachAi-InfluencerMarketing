"use client";

import { useState } from "react";
import { Check, Pencil, Sparkles, X } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { btn, btnPrimary, textarea } from "@/lib/ui";
import { PROPOSAL_ACTION, type Proposal } from "@/data/deals";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

function errorText(e: unknown, fallback: string) {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

/** One suggested next step: what, why, the message (editable), and Approve / Edit / Skip. */
export function ProposalCard({ p, api, onDone, onOpen, selected, onSelect, text: liftedText, onText }: {
  p: Proposal;
  api: Api;
  onDone: (data: { proposals?: Proposal[] }) => void;
  onOpen?: () => void; // open the deal (from the To do list)
  selected?: boolean; // the To do list's bulk selection
  onSelect?: () => void;
  text?: string; // the message as edited, kept by the list so "Approve selected" sends your edits
  onText?: (t: string) => void;
}) {
  const [ownText, setOwnText] = useState(p.message ?? "");
  const text = liftedText ?? ownText;
  const setText = (t: string) => (onText ? onText(t) : setOwnText(t));
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<"approve" | "skip" | "reword" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState(p.source);

  const approve = async () => {
    setBusy("approve");
    setError(null);
    try {
      if (p.is_message) {
        try {
          await navigator.clipboard.writeText(text);
        } catch {} // copying can be blocked; the message stays on the timeline either way
      }
      const r = await api(`/api/proposals/${p.id}/approve`, { method: "POST", data: { message: p.is_message ? text : null } });
      onDone(r.data as { proposals?: Proposal[] });
    } catch (e) {
      setError(errorText(e, "Couldn't do that. Try again."));
      setBusy(null);
    }
  };

  const skip = async () => {
    setBusy("skip");
    try {
      const r = await api(`/api/proposals/${p.id}/skip`, { method: "POST" });
      onDone(r.data as { proposals?: Proposal[] });
    } catch (e) {
      setError(errorText(e, "Couldn't skip it. Try again."));
      setBusy(null);
    }
  };

  const reword = async () => {
    setBusy("reword");
    setError(null);
    try {
      const r = (await api(`/api/proposals/${p.id}/reword`, { method: "POST" })).data as { message: string; source: "ai" | "template" };
      if (r.source === "ai") {
        setText(r.message);
        setSource("ai");
        onDone({}); // saved on the server: refresh so the same suggestion shows the new wording everywhere
      } else setError("The AI wording changed a number, so we kept ours.");
    } catch (e) {
      setError(errorText(e, "Couldn't reword it."));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={`rounded-lg border bg-white dark:bg-[#0c0d0e] p-3 space-y-2.5 transition-colors ${selected ? "border-zinc-400 dark:border-zinc-500" : "border-zinc-200 dark:border-zinc-800"}`}>
      <div className="flex items-start gap-2.5 min-w-0">
        {onSelect && (
          <input type="checkbox" checked={!!selected} onChange={onSelect} aria-label={`Select ${p.name}`} className="mt-2 accent-zinc-900 dark:accent-zinc-100 shrink-0" />
        )}
        {onOpen && (
          <button type="button" onClick={onOpen} aria-label={`Open ${p.name}`} className="shrink-0">
            <CreatorAvatar
              name={p.name}
              src={p.avatar_url}
              className="w-7 h-7 rounded-[6px] border border-zinc-200 dark:border-white/10 bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-center"
              textClassName="text-[11px] font-medium"
            />
          </button>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">
            {onOpen && (
              <button type="button" onClick={onOpen} className="hover:underline underline-offset-4 decoration-zinc-300 dark:decoration-zinc-600">{p.name}</button>
            )}
            {onOpen && <span className="text-zinc-400"> · </span>}
            {p.title}
          </p>
          {p.reason && <p className="text-[11px] text-zinc-500 leading-relaxed mt-0.5">{p.reason}</p>}
        </div>
      </div>

      {p.is_message && (
        editing ? (
          <textarea value={text} onChange={(e) => setText(e.target.value.slice(0, 2700))} rows={6} aria-label="Message" className={textarea} autoFocus />
        ) : (
          <div className="rounded-md bg-zinc-100 dark:bg-[#121314] px-3 py-2">
            <p className="text-xs whitespace-pre-wrap leading-relaxed text-zinc-800 dark:text-zinc-200">{text}</p>
            {source === "ai" && <p className="text-[11px] text-zinc-500 mt-1.5">Worded by AI · numbers checked</p>}
          </div>
        )
      )}

      {error && <p className="text-[11px] text-rose-500">{error}</p>}

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={approve} disabled={!!busy || (p.is_message && !text.trim())} className={btnPrimary}>
          <Check size={13} /> {busy === "approve" ? "Working…" : p.kind === "agree" && p.is_message ? "Copy and agree" : PROPOSAL_ACTION[p.kind]}
        </button>
        {p.is_message && (
          <button type="button" onClick={() => setEditing((v) => !v)} disabled={!!busy} className={btn}>
            <Pencil size={12} /> {editing ? "Done" : "Edit"}
          </button>
        )}
        {p.can_reword && !editing && (
          <button type="button" onClick={reword} disabled={!!busy} className={btn}>
            <Sparkles size={12} className="text-violet-500" /> {busy === "reword" ? "Rewording…" : "Reword with AI"}
          </button>
        )}
        <button type="button" onClick={skip} disabled={!!busy} className={`${btn} ml-auto border-transparent text-zinc-500`}>
          <X size={12} /> Skip
        </button>
      </div>
    </div>
  );
}

/** The Deals tab's "To do" view: every suggested next step across this campaign's deals, with bulk actions.
 * Nothing happens until you approve; edits you make in a card are what gets approved. */
export function NeedsYou({ proposals, api, onDone, onOpen }: {
  proposals: Proposal[];
  api: Api;
  onDone: (data: { proposals?: Proposal[] }) => void;
  onOpen: (dealId: string) => void;
}) {
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"approve" | "skip" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const live = new Set(proposals.map((p) => p.id));
  const chosen = proposals.filter((p) => picked.has(p.id) && live.has(p.id));
  const messages = chosen.filter((p) => p.is_message).length;
  const toggle = (id: string) => setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const bulk = async (what: "approve" | "skip") => {
    setBusy(what);
    setError(null);
    let last: { proposals?: Proposal[] } = {};
    let failed = 0;
    for (const p of chosen) {
      try {
        const data = what === "approve" ? { message: p.is_message ? edits[p.id] ?? p.message : null } : undefined;
        last = (await api(`/api/proposals/${p.id}/${what}`, { method: "POST", data })).data as { proposals?: Proposal[] };
      } catch {
        failed += 1;
      }
    }
    setPicked(new Set());
    setBusy(null);
    if (failed) setError(`${failed} couldn't be done. They're still in the list.`);
    onDone(last);
  };

  if (proposals.length === 0)
    return (
      <div className="rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 px-4 py-10 text-center">
        <p className="text-[13px] text-zinc-900 dark:text-zinc-100">Nothing to do right now</p>
        <p className="text-xs text-zinc-500 mt-1">When a creator replies, open their deal and paste it in. We&apos;ll suggest what to do next.</p>
      </div>
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 min-h-[30px]">
        <label className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400 mr-1">
          <input
            type="checkbox"
            checked={chosen.length === proposals.length}
            onChange={() => setPicked(chosen.length === proposals.length ? new Set() : new Set(proposals.map((p) => p.id)))}
            className="accent-zinc-900 dark:accent-zinc-100"
          />
          {chosen.length ? `${chosen.length} selected` : "Select all"}
        </label>
        {chosen.length > 0 && (
          <>
            <button type="button" onClick={() => bulk("approve")} disabled={!!busy} className={btnPrimary}>
              <Check size={13} /> {busy === "approve" ? "Approving…" : `Approve ${chosen.length}`}
            </button>
            <button type="button" onClick={() => bulk("skip")} disabled={!!busy} className={btn}>
              {busy === "skip" ? "Skipping…" : "Skip"}
            </button>
            {messages > 0 && <span className="text-[11px] text-zinc-500">{messages === 1 ? "1 message is" : `${messages} messages are`} marked sent. Send them yourself until Gmail is connected.</span>}
          </>
        )}
      </div>
      {error && <p className="text-[11px] text-rose-500">{error}</p>}
      <div className="grid gap-2.5 lg:grid-cols-2">
        {proposals.map((p) => (
          <ProposalCard
            key={`${p.id}:${p.message}`}
            p={p}
            api={api}
            onDone={onDone}
            onOpen={() => onOpen(p.deal_id)}
            selected={picked.has(p.id)}
            onSelect={() => toggle(p.id)}
            text={edits[p.id] ?? p.message ?? ""}
            onText={(t) => setEdits((e) => ({ ...e, [p.id]: t }))}
          />
        ))}
      </div>
    </div>
  );
}
