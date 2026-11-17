"use client";

import { useEffect, useState } from "react";
import { Loader2, Search, X } from "lucide-react";
import { missingFields, transformPayload } from "@/app/campaign/[id]/details/SubmitCampaignButton";
import { useCampaignStore } from "@/store/campaignStore";
import { useApi } from "@/lib/api";
import { btn } from "@/lib/ui";

type Strategy = { topics: string[]; youtube_queries: string[]; [key: string]: unknown };

const QUERY_WORDS: [number, number] = [2, 5];
const QUERY_COUNT: [number, number] = [6, 12];
const TOPIC_COUNT: [number, number] = [3, 8];
const words = (q: string) => q.trim().split(/\s+/).filter(Boolean).length;

function Chips({ label, hint, items, onChange, placeholder, max, problem }: {
  label: string; hint: string; items: string[]; onChange: (v: string[]) => void; placeholder: string; max: number; problem: string | null;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim().replace(/,$/, "").slice(0, 60);
    if (v.length >= 2 && items.length < max && !items.some((x) => x.toLowerCase() === v.toLowerCase())) onChange([...items, v]);
    setDraft("");
  };
  return (
    <div className="space-y-1.5">
      <p className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">{label}</p>
      <div className="flex flex-wrap items-center gap-1.5 min-h-[34px] rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] px-2 py-1.5 focus-within:border-zinc-400 dark:focus-within:border-zinc-600">
        {items.map((c) => (
          <span key={c} className="inline-flex items-center gap-1 rounded-[4px] bg-zinc-100 dark:bg-zinc-800/70 px-1.5 py-0.5 text-xs text-zinc-800 dark:text-zinc-200">
            {c}
            <button type="button" aria-label={`Remove ${c}`} onClick={() => onChange(items.filter((x) => x !== c))} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"><X size={11} /></button>
          </span>
        ))}
        <input aria-label={`Add to ${label}`} value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={add} placeholder={items.length ? "" : placeholder}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); }
            if (e.key === "Backspace" && !draft && items.length) onChange(items.slice(0, -1));
          }}
          disabled={items.length >= max}
          className="flex-1 min-w-[110px] bg-transparent text-xs text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none" />
      </div>
      <p className={`text-[11px] ${problem ? "text-rose-500" : "text-zinc-500"}`}>{problem ?? hint}</p>
    </div>
  );
}

/** "How we'll search" (F1.24b): the strategy ReachAI will use, shown before any credits are spent. Optional, and editable. An edit
 * goes with the search as `chosen_strategy`; without one the search reuses the preview, so it costs nothing extra. */
export default function StrategyPreview() {
  const api = useApi();
  const store = useCampaignStore();
  const setField = useCampaignStore((s) => s.setField);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [original, setOriginal] = useState<Strategy | null>(null);
  const [draft, setDraft] = useState<Strategy | null>(null);
  const [forKey, setForKey] = useState("");
  const key = JSON.stringify(transformPayload(store));

  // the strategy depends on the brief: if the brief changes, the preview (and an edit of it) no longer applies
  useEffect(() => {
    if (original && key !== forKey) {
      setOriginal(null);
      setDraft(null);
      setField("chosenStrategy", null);
      setError("You changed the brief, so the preview was cleared. Preview again to see the new search.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only when the brief changes
  }, [key]);

  async function load() {
    const missing = missingFields(store);
    if (missing.length) return setError(`Fill in ${missing.join(", ")} first, then preview.`);
    setBusy(true);
    setError(null);
    try {
      const s = ((await api("/api/campaigns/strategy-preview", { method: "POST", data: { details: transformPayload(store) } })).data as { strategy: Strategy }).strategy;
      setOriginal(s);
      setDraft(s);
      setForKey(key);
      setField("chosenStrategy", null);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(typeof detail === "string" ? detail : "We couldn't prepare the preview. You can still start the search.");
    } finally {
      setBusy(false);
    }
  }

  function change(next: Strategy) {
    setDraft(next);
    setField("chosenStrategy", JSON.stringify(next) === JSON.stringify(original) ? null : next);
  }

  const badQuery = draft?.youtube_queries.find((q) => words(q) < QUERY_WORDS[0] || words(q) > QUERY_WORDS[1]);
  const queryProblem = !draft ? null
    : draft.youtube_queries.length < QUERY_COUNT[0] || draft.youtube_queries.length > QUERY_COUNT[1] ? `Keep between ${QUERY_COUNT[0]} and ${QUERY_COUNT[1]} searches.`
    : badQuery ? `"${badQuery}" should be ${QUERY_WORDS[0]}–${QUERY_WORDS[1]} words.` : null;
  const topicProblem = !draft ? null
    : draft.topics.length < TOPIC_COUNT[0] || draft.topics.length > TOPIC_COUNT[1] ? `Keep between ${TOPIC_COUNT[0]} and ${TOPIC_COUNT[1]} topics.` : null;
  const edited = !!store.chosenStrategy;

  return (
    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg p-4 bg-white dark:bg-[#0c0d0e] space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-900 dark:text-zinc-100"><Search size={13} className="text-zinc-500" /> How we&apos;ll search</div>
          <p className="text-[11px] text-zinc-500">Optional. See what ReachAI will look for before it uses any credits, and change it if it&apos;s off.</p>
        </div>
        {!draft && (
          <button type="button" className={btn} onClick={() => { setOpen(true); load(); }} disabled={busy}>
            {busy && <Loader2 size={12} className="animate-spin" />} Preview
          </button>
        )}
      </div>
      {error && <p className="text-[11px] text-rose-500">{error}</p>}
      {open && draft && original && (
        <div className="space-y-4 pt-1">
          <Chips label="Topics we look for" hint="The subjects your buyers watch. Add or remove any." items={draft.topics} max={TOPIC_COUNT[1]}
            onChange={(topics) => change({ ...draft, topics })} placeholder="e.g. data science career" problem={topicProblem} />
          <Chips label="Searches on YouTube" hint={`${QUERY_WORDS[0]}–${QUERY_WORDS[1]} words each, ${QUERY_COUNT[0]} to ${QUERY_COUNT[1]} of them. Describe the niche, not your brand.`}
            items={draft.youtube_queries} max={QUERY_COUNT[1]} onChange={(youtube_queries) => change({ ...draft, youtube_queries })}
            placeholder="e.g. machine learning roadmap" problem={queryProblem} />
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] text-zinc-500">
              {edited ? "Your changes are used for this search." : "This is what the search will use. Starting it costs the same."}
            </p>
            {edited && <button type="button" className={btn} onClick={() => change(original)}>Start over</button>}
          </div>
        </div>
      )}
    </div>
  );
}
