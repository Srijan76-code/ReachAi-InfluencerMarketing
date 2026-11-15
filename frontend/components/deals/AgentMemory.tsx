"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
type Memory = { id: string; kind: "fact" | "style" | "lesson"; text: string; campaign_id: string | null; source: string | null };

const GROUPS: { kind: Memory["kind"]; title: string; empty: string }[] = [
  { kind: "fact", title: "Your answers", empty: "When a creator asks something ReachAI doesn't know, it asks you. Your answers show up here." },
  { kind: "style", title: "How you write", empty: "Rules learned from messages you edited before sending." },
  { kind: "lesson", title: "Checks it keeps in mind", empty: "Checks your drafts failed more than once." },
];

/** What the reply agent has learned for you. Anything wrong can be switched off, so it never sticks. */
export function AgentMemory({ api, open, onOpenChange }: { api: Api; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [items, setItems] = useState<Memory[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api("/api/agent/memory").then((r) => setItems((r.data as Memory[]) ?? [])).catch(() => setItems([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [open]);

  const forget = async (id: string) => {
    setBusy(id);
    try {
      await api(`/api/agent/memory/${id}`, { method: "DELETE" });
      setItems((xs) => (xs ?? []).filter((m) => m.id !== id));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
        <DialogHeader>
          <DialogTitle className="text-sm">What ReachAI remembers</DialogTitle>
          <DialogDescription className="text-xs">Used when it writes replies for you. Remove anything that&apos;s wrong.</DialogDescription>
        </DialogHeader>
        {items === null ? (
          <div className="py-6 flex justify-center"><Loader2 size={16} className="animate-spin text-zinc-400" /></div>
        ) : (
          <div className="space-y-4 max-h-[60vh] overflow-y-auto">
            {GROUPS.map((g) => {
              const xs = items.filter((m) => m.kind === g.kind);
              return (
                <section key={g.kind}>
                  <h3 className="text-[11px] font-medium text-zinc-500 mb-1.5">{g.title}</h3>
                  {xs.length === 0 ? <p className="text-xs text-zinc-400">{g.empty}</p> : (
                    <ul className="space-y-1">
                      {xs.map((m) => (
                        <li key={m.id} className="group flex items-start gap-2 rounded-lg px-2.5 py-1.5 bg-zinc-50 dark:bg-zinc-900/60 text-xs text-zinc-800 dark:text-zinc-200">
                          <span className="flex-1 min-w-0 break-words">{m.text}</span>
                          <button type="button" onClick={() => forget(m.id)} disabled={busy === m.id} aria-label="Forget this"
                            className="shrink-0 text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-100">
                            {busy === m.id ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
