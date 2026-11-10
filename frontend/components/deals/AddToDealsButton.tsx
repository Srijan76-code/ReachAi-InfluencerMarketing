"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Handshake } from "lucide-react";
import { useApi } from "@/lib/api";
import { btn } from "@/lib/ui";

/** "Add to outreach" for one or more creators (creator panel, selection bar): each gets a chat in Outreach. */
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
      setNote(added ? (creatorIds.length > 1 ? `${added} added` : "In Outreach") : "Already in Outreach");
      setState("done");
    } catch {
      setState("error");
    }
  };

  const base =
    variant === "panel"
      ? btn
      : "px-2.5 py-1 font-medium rounded-full border border-zinc-600 text-zinc-100 hover:bg-white/10 flex items-center gap-1.5";

  if (state === "done")
    return (
      <Link href={`/campaign/${campaignId}/outreach`} className={base} title="Open Outreach">
        <Check size={12} className="text-emerald-500" /> {note}
      </Link>
    );
  return (
    <button type="button" onClick={add} disabled={state === "busy" || !creatorIds.length} className={`${base} disabled:opacity-50`} title="Give each a chat in Outreach">
      <Handshake size={12} />
      {state === "busy" ? "Adding…" : state === "error" ? "Try again" : creatorIds.length > 1 ? `Add ${creatorIds.length} to outreach` : "Add to outreach"}
    </button>
  );
}
