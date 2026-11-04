"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Check, Loader2, Mail, Send } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Field } from "@/components/ui/field";
import { useApi } from "@/lib/api";
import { btn, btnPrimary, control, textarea } from "@/lib/ui";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
export type GmailStatus = { configured: boolean; connected: boolean; email: string | null; needs_reconnect: boolean; sent_today: number; daily_cap: number };

const RESULT: Record<string, string> = {
  connected: "Gmail connected. Approved messages now go from your address.",
  cancelled: "Gmail wasn't connected.",
  expired: "That took too long. Try connecting Gmail again.",
  missing_permission: "Gmail needs both permissions (send, and read replies in threads ReachAI starts). Try again and leave both ticked.",
  failed: "Couldn't connect Gmail. Try again.",
};

/** The founder's Gmail connection, shared by Deals and Outreach. */
export function useGmail(apiOverride?: Api) {
  const signedInApi = useApi();
  const api = apiOverride ?? signedInApi;
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const load = useCallback(
    () => api("/api/gmail").then((r) => setStatus(r.data as GmailStatus)).catch(() => setStatus(null)),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
    [],
  );
  useEffect(() => {
    load();
  }, [load]);
  const connect = async () => {
    const r = (await api("/api/gmail/connect", { method: "POST", data: { return_to: window.location.pathname } })).data as { url: string };
    window.location.href = r.url;
  };
  const disconnect = async () => {
    await api("/api/gmail", { method: "DELETE" });
    load();
  };
  return { status, connect, disconnect, reload: load, ready: !!status?.connected && !status.needs_reconnect };
}

/** "Connect Gmail" button, or the connected address with a menu. Shows the result after Google sends you back. */
export function GmailConnect({ gmail }: { gmail: ReturnType<typeof useGmail> }) {
  const { status, connect, disconnect } = gmail;
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const r = p.get("gmail");
    if (!r) return;
    setNote(RESULT[r] ?? null); // eslint-disable-line react-hooks/set-state-in-effect -- read once from the URL Google sent us back to
    p.delete("gmail");
    window.history.replaceState(null, "", window.location.pathname + (p.toString() ? `?${p}` : ""));
  }, []);
  if (!status?.configured) return null;
  return (
    <div className="flex items-center gap-2 min-w-0">
      {note && <span className="text-[11px] text-zinc-500 truncate max-w-[320px]" title={note}>{note}</span>}
      {status.connected && !status.needs_reconnect ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" className={btn} title="Approved messages are sent from this address">
              <Mail size={13} /> <span className="max-w-[180px] truncate">{status.email}</span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60 bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800">
            <DropdownMenuLabel className="text-[11px] font-normal text-zinc-500">
              Sent today: {status.sent_today} of {status.daily_cap}. Replies are checked when you open Deals and every 30 minutes.
            </DropdownMenuLabel>
            <DropdownMenuItem className="text-xs cursor-pointer text-rose-500 focus:text-rose-500" onSelect={() => disconnect()}>
              Disconnect Gmail
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await connect();
            } catch {
              setBusy(false);
              setNote("Couldn't start connecting Gmail. Try again.");
            }
          }}
          className={btn}
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Mail size={13} />} {status.needs_reconnect ? "Reconnect Gmail" : "Connect Gmail"}
        </button>
      )}
    </div>
  );
}

/** Send an approved first pitch from Outreach: editable to, subject and body; starts the creator's deal. */
export function SendPitch({ campaignId, creatorId, subject, body, leadEmail }: {
  campaignId: string;
  creatorId: string;
  subject: string;
  body: string;
  leadEmail: string | null;
}) {
  const api = useApi();
  const gmail = useGmail();
  const [to, setTo] = useState(leadEmail ?? "");
  const [subj, setSubj] = useState(subject);
  const [text, setText] = useState(body);
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    setState("sending");
    setError(null);
    try {
      await api(`/api/campaigns/${campaignId}/outreach/send`, { method: "POST", data: { creator_id: creatorId, subject: subj, body: text, to: to || null } });
      setState("sent");
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Couldn't send it. Try again.");
      setState("idle");
    }
  };

  if (state === "sent")
    return (
      <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 flex items-center justify-between gap-3">
        <p className="text-xs text-emerald-700 dark:text-emerald-400 flex items-center gap-2"><Check size={13} /> Sent from {gmail.status?.email}. Their reply will show up in Deals.</p>
        <Link href={`/campaign/${campaignId}/deals`} className={btn}>Open Deals</Link>
      </div>
    );

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="To">
          <input value={to} onChange={(e) => setTo(e.target.value.trim())} placeholder="their@email.com" className={control} />
        </Field>
        <Field label="Subject">
          <input value={subj} onChange={(e) => setSubj(e.target.value)} className={control} />
        </Field>
      </div>
      <Field label="Message">
        <textarea value={text} onChange={(e) => setText(e.target.value.slice(0, 5000))} rows={10} className={textarea} />
      </Field>
      {error && <p className="text-[11px] text-rose-500">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        {gmail.ready ? (
          <button type="button" onClick={send} disabled={state === "sending" || !to || !subj.trim() || !text.trim()} className={btnPrimary}>
            {state === "sending" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} {state === "sending" ? "Sending" : `Send from ${gmail.status?.email}`}
          </button>
        ) : (
          <GmailConnect gmail={gmail} />
        )}
        {to && (
          <a href={`mailto:${to}?subject=${encodeURIComponent(subj)}&body=${encodeURIComponent(text)}`} className="text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 underline underline-offset-4">
            Or open in your mail app
          </a>
        )}
      </div>
    </div>
  );
}
