"use client";

import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { useApi } from "@/lib/api";

type Grant = {
  id: string;
  label: string;
  what: string;
  campaign_name: string | null;
  client_name: string;
  status: "pending" | "approved";
  mode: "ask" | "unattended";
  can_unattended: boolean;
  valid_until: string | null;
  user_code: string | null;
};

/** What the founder has allowed their agents (F9.8, 8b): each permission, when it ends, and a way to remove it. */
export function AgentPermissions() {
  const api = useApi();
  const [grants, setGrants] = useState<Grant[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setGrants(((await api("/api/grants")).data as { grants: Grant[] }).grants);
    } catch {
      setGrants([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function remove(g: Grant) {
    if (!window.confirm(`Remove "${g.label}"${g.campaign_name ? ` in ${g.campaign_name}` : ""}? Your agent stops being able to do it.`)) return;
    try {
      await api(`/api/grants/${g.id}`, { method: "DELETE" });
      await load();
    } catch {
      setError("Couldn't remove it. Try again.");
    }
  }

  if (grants === null) return null;
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">What your agents may do</h2>
        <p className="text-[11px] text-zinc-500">Permissions you approved, and requests waiting for you. Everything else, your agent can only read and draft.</p>
      </div>
      {grants.length === 0 ? (
        <p className="text-[11px] text-zinc-500">Nothing yet. When your agent asks for something, it gives you a link to approve.</p>
      ) : (
        <ul className="divide-y divide-zinc-200 dark:divide-zinc-800 border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-[#0c0d0e]">
          {grants.map((g) => (
            <li key={g.id} className="flex items-start gap-3 p-3">
              <div className="flex-1 min-w-0 space-y-0.5">
                <p className="text-[13px] text-zinc-900 dark:text-zinc-100">
                  {g.label}
                  {g.campaign_name ? <span className="text-zinc-500"> · {g.campaign_name}</span> : null}
                </p>
                <p className="text-[11px] text-zinc-500">
                  {g.client_name} ·{" "}
                  {g.status === "pending"
                    ? `waiting for you (code ${g.user_code})`
                    : `until ${g.valid_until ? new Date(g.valid_until).toLocaleDateString() : "?"}${g.can_unattended ? (g.mode === "unattended" ? " · by itself" : " · you say yes each time") : ""}`}
                </p>
              </div>
              <button type="button" onClick={() => remove(g)} aria-label={`Remove ${g.label}`}
                className="inline-flex items-center justify-center h-[30px] w-[30px] rounded-md border border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:text-rose-600 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors">
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="text-[11px] text-rose-500">{error}</p>}
    </section>
  );
}
