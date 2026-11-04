"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Handshake } from "lucide-react";
import { useApi } from "@/lib/api";

/** "Add to deals" for one or more creators (creator panel, selection bar). After adding, it links to the Deals tab. */
export function AddToDealsButton({ campaignId, creatorIds, variant = "panel" }: {
  campaignId: string;
  creatorIds: string[];
  variant?: "panel" | "bar";
}) {
  const api = useApi();
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [note, setNote] = useState("");

  const add = async () => {
    setState("busy");
    try {
      const r = await api(`/api/campaigns/${campaignId}/deals`, { method: "POST", data: { creator_ids: creatorIds } });
      const d = r.data as { created?: unknown[]; skipped?: number };
      const added = d.created?.length ?? 0;
      setNote(added ? (creatorIds.length > 1 ? `${added} added` : "In deals") : "Already in deals");
      setState("done");
    } catch {
      setState("error");
    }
  };

  const base =
    variant === "panel"
      ? "h-[34px] px-3 text-[12px] font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-800 dark:text-zinc-200 flex items-center gap-1.5"
      : "px-2.5 py-1 font-medium rounded-full border border-zinc-600 text-zinc-100 hover:bg-white/10 flex items-center gap-1.5";

  if (state === "done")
    return (
      <Link href={`/campaign/${campaignId}/deals`} className={base} title="Open the Deals tab">
        <Check size={12} className="text-emerald-500" /> {note}
      </Link>
    );
  return (
    <button type="button" onClick={add} disabled={state === "busy" || !creatorIds.length} className={`${base} disabled:opacity-50`} title="Track them on the Deals tab">
      <Handshake size={12} />
      {state === "busy" ? "Adding…" : state === "error" ? "Try again" : creatorIds.length > 1 ? `Add ${creatorIds.length} to deals` : "Add to deals"}
    </button>
  );
}
