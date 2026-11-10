"use client";

import { useEffect, useState } from "react";
import { MessageSquare, ThumbsDown, ThumbsUp } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { FeedbackItem } from "@/data/influencerList";
import { updatedLabel } from "@/types/campaign";

/** Reviewer feedback (roadmap F1.18b): what people you shared with said about each creator. */

function counts(items: FeedbackItem[]) {
  return {
    yes: items.filter((f) => f.verdict === "yes").length,
    no: items.filter((f) => f.verdict === "no").length,
    comments: items.filter((f) => f.comment).length,
  };
}

/** Owner's row: "👍 2 · 👎 1 · 💬 1", with who said what on hover. */
export function FeedbackChip({ items }: { items?: FeedbackItem[] }) {
  if (!items?.length) return null;
  const c = counts(items);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="flex-shrink-0 inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded-[4px] border border-zinc-200 dark:border-zinc-700 text-[9px] font-bold text-zinc-600 dark:text-zinc-300 cursor-help whitespace-nowrap">
          {c.yes > 0 && <span className="flex items-center gap-0.5 text-emerald-600 dark:text-emerald-400"><ThumbsUp size={9} />{c.yes}</span>}
          {c.no > 0 && <span className="flex items-center gap-0.5 text-rose-500"><ThumbsDown size={9} />{c.no}</span>}
          {c.comments > 0 && <span className="flex items-center gap-0.5"><MessageSquare size={9} />{c.comments}</span>}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[260px] text-xs">
        <FeedbackLines items={items} />
      </TooltipContent>
    </Tooltip>
  );
}

function FeedbackLines({ items }: { items: FeedbackItem[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((f, i) => (
        <li key={i}>
          <span className="font-semibold">{f.by || "A reviewer"}</span>{" "}
          {f.verdict === "yes" ? "👍" : f.verdict === "no" ? "👎" : ""}
          {f.comment && <span className="block opacity-90">“{f.comment}”</span>}
        </li>
      ))}
    </ul>
  );
}

/** Owner's panel: the feedback on one creator, newest first. */
export function FeedbackSection({ items }: { items?: FeedbackItem[] }) {
  if (!items?.length) return null;
  const c = counts(items);
  return (
    <section className="space-y-3">
      <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
        <MessageSquare size={14} className="text-violet-500" />
        Feedback
        <span className="ml-auto normal-case tracking-normal font-medium text-[11px] text-zinc-500">
          {c.yes} approved · {c.no} rejected
        </span>
      </h3>
      <ul className="rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-100 dark:bg-[#121314] divide-y divide-zinc-200/60 dark:divide-zinc-800/60">
        {items.map((f, i) => (
          <li key={i} className="p-3 flex gap-2.5">
            <span className="mt-0.5 shrink-0">
              {f.verdict === "yes" ? <ThumbsUp size={13} className="text-emerald-500" /> : f.verdict === "no" ? <ThumbsDown size={13} className="text-rose-500" /> : <MessageSquare size={13} className="text-zinc-400" />}
            </span>
            <div className="min-w-0">
              <p className="text-[12px] text-zinc-800 dark:text-zinc-200">
                <span className="font-medium">{f.by || "A reviewer"}</span>
                <span className="text-zinc-500"> · {f.verdict === "yes" ? "approved" : f.verdict === "no" ? "rejected" : "commented"}{f.updated_at ? ` ${updatedLabel(f.updated_at)}` : ""}</span>
              </p>
              {f.comment && <p className="text-[12px] text-zinc-600 dark:text-zinc-400 mt-0.5">“{f.comment}”</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export type MyFeedback = { verdict: "yes" | "no" | null; comment: string | null };

/** Reviewer's 👍 / 👎 next to a creator on a shared page. Clicking the chosen one again clears it. */
export function VerdictButtons({ value, onChange, name }: { value?: MyFeedback; onChange: (v: MyFeedback) => void; name: string }) {
  const verdict = value?.verdict ?? null;
  const set = (v: "yes" | "no") => onChange({ verdict: verdict === v ? null : v, comment: value?.comment ?? null });
  const base = "h-8 w-8 flex items-center justify-center rounded-md border transition-colors";
  return (
    <div className="flex flex-col gap-1" role="group" aria-label={`Your verdict on ${name}`}>
      <button type="button" aria-pressed={verdict === "yes"} title="Approve" onClick={() => set("yes")}
        className={`${base} ${verdict === "yes" ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "border-zinc-200 dark:border-zinc-800 text-zinc-400 hover:text-emerald-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}>
        <ThumbsUp size={14} />
      </button>
      <button type="button" aria-pressed={verdict === "no"} title="Reject" onClick={() => set("no")}
        className={`${base} ${verdict === "no" ? "border-rose-500/40 bg-rose-500/10 text-rose-500" : "border-zinc-200 dark:border-zinc-800 text-zinc-400 hover:text-rose-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}>
        <ThumbsDown size={14} />
      </button>
    </div>
  );
}

/** Reviewer's box in the creator panel: verdict + comment, saved when they press Save. */
export function ReviewBox({ value, onSave }: { value?: MyFeedback; onSave: (v: MyFeedback) => Promise<boolean> }) {
  const [verdict, setVerdict] = useState<MyFeedback["verdict"]>(value?.verdict ?? null);
  const [comment, setComment] = useState(value?.comment ?? "");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  useEffect(() => {
    setVerdict(value?.verdict ?? null);
    setComment(value?.comment ?? "");
  }, [value?.verdict, value?.comment]);
  const save = async () => {
    setState("saving");
    setState((await onSave({ verdict, comment: comment.trim() || null })) ? "saved" : "error");
  };
  const pill = (v: "yes" | "no", label: string, Icon: typeof ThumbsUp, on: string) => (
    <button type="button" aria-pressed={verdict === v} onClick={() => setVerdict(verdict === v ? null : v)}
      className={`flex items-center gap-1.5 px-3 h-8 rounded-md border text-xs font-medium transition-colors ${verdict === v ? on : "border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}>
      <Icon size={13} /> {label}
    </button>
  );
  return (
    <section className="space-y-2.5 rounded border border-violet-500/20 bg-violet-500/5 p-3.5">
      <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Your feedback</h3>
      <div className="flex gap-2">
        {pill("yes", "Approve", ThumbsUp, "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400")}
        {pill("no", "Reject", ThumbsDown, "border-rose-500/40 bg-rose-500/10 text-rose-500")}
      </div>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value.slice(0, 500))}
        rows={2}
        placeholder="Add a comment for the person who shared this (optional)"
        aria-label="Comment"
        className="w-full px-2.5 py-2 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-zinc-400 resize-none"
      />
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-zinc-500">
          {state === "saved" ? "Saved. The owner can see it." : state === "error" ? "Couldn't save. Try again." : "Only the person who shared this sees your feedback."}
        </span>
        <button type="button" onClick={save} disabled={state === "saving"}
          className="h-8 px-3 text-xs font-medium rounded-md bg-zinc-900 text-white dark:bg-zinc-300 dark:text-zinc-900 hover:opacity-90 disabled:opacity-50">
          {state === "saving" ? "Saving…" : "Save"}
        </button>
      </div>
    </section>
  );
}
