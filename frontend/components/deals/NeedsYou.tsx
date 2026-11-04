"use client";

import { useState } from "react";
import { Check, Pencil, Sparkles, X } from "lucide-react";
import { CreatorAvatar } from "@/components/CreatorAvatar";
import { SectionHeader } from "@/components/ui/stat";
import { btn, btnPrimary, textarea } from "@/lib/ui";
import { PROPOSAL_ACTION, type Proposal } from "@/data/deals";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

function errorText(e: unknown, fallback: string) {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

/** One suggested next step: what, why, the message (editable), and Approve / Edit / Skip. */
export function ProposalCard({ p, api, onDone, onOpen }: {
  p: Proposal;
  api: Api;
  onDone: (data: { proposals?: Proposal[] }) => void;
  onOpen?: () => void; // open the deal (from the board's list)
}) {
  const [text, setText] = useState(p.message ?? "");
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
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] p-3 space-y-2.5">
      <div className="flex items-start gap-2.5 min-w-0">
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

/** The board's "Needs you" list: every suggested next step across this campaign's deals. */
export function NeedsYou({ proposals, api, onDone, onOpen }: {
  proposals: Proposal[];
  api: Api;
  onDone: (data: { proposals?: Proposal[] }) => void;
  onOpen: (dealId: string) => void;
}) {
  return (
    <section className="space-y-2.5">
      <SectionHeader right={<span className="text-[11px] text-zinc-500">Nothing happens until you approve it</span>}>
        <span className="flex items-center gap-2">
          Needs you
          {proposals.length > 0 && (
            <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-[10px] font-semibold flex items-center justify-center tracking-normal">
              {proposals.length}
            </span>
          )}
        </span>
      </SectionHeader>
      {proposals.length === 0 ? (
        <p className="text-xs text-zinc-500">Nothing needs you right now. When a creator answers, paste their reply in their deal and we&apos;ll suggest the next step.</p>
      ) : (
        <div className="grid gap-2.5 md:grid-cols-2">
          {proposals.map((p) => (
            <ProposalCard key={`${p.id}:${p.message}`} p={p} api={api} onDone={onDone} onOpen={() => onOpen(p.deal_id)} />
          ))}
        </div>
      )}
    </section>
  );
}
