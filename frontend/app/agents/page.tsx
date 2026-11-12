"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Check, Copy, KeyRound, Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApi } from "@/lib/api";
import { OnboardAgent } from "@/components/OnboardAgent";

type ApiKey = {
  key_id: string;
  name: string;
  prefix: string;
  created_at: string | null;
  last_used_at: string | null;
};

type NewKey = ApiKey & { key: string };

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard blocked: the text stays visible so it can be selected by hand.
        }
      }}
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {copied ? "Copied" : label}
    </Button>
  );
}

function Snippet({ title, code }: { title: string; code: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 dark:border-neutral-800 p-3">
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-xs font-medium text-neutral-700 dark:text-neutral-300">{title}</p>
        <CopyButton text={code} />
      </div>
      <pre className="text-xs overflow-x-auto whitespace-pre-wrap break-all text-neutral-600 dark:text-neutral-400">
        {code}
      </pre>
    </div>
  );
}

const formatDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "Never";

export default function AgentsPage() {
  const api = useApi();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<NewKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [origin, setOrigin] = useState("https://reach-ai-influencer-marketing.vercel.app");

  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);
  const mcpUrl = `${origin}/api/mcp`;

  const loadKeys = useCallback(async () => {
    try {
      const res = await api("/api/keys", { method: "GET" });
      setKeys(Array.isArray(res.data) ? res.data : []);
    } catch {
      setError("Could not load your keys. Refresh and try again.");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    loadKeys();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createKey = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setCreating(true);
    setError(null);
    try {
      const res = await api("/api/keys", { method: "POST", data: { name: trimmed } });
      setNewKey(res.data as NewKey);
      setName("");
      await loadKeys();
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(detail ?? "Could not create the key. Try again.");
    } finally {
      setCreating(false);
    }
  };

  const revokeKey = async (key: ApiKey) => {
    if (!window.confirm(`Revoke "${key.name}"? Any agent using it will stop working.`)) return;
    try {
      await api(`/api/keys/${key.key_id}`, { method: "DELETE" });
      if (newKey?.key_id === key.key_id) setNewKey(null);
      await loadKeys();
    } catch {
      setError("Could not revoke the key. Try again.");
    }
  };

  const keyForSnippets = newKey?.key ?? "YOUR_KEY";

  return (
    <main className="max-w-3xl mx-auto px-6 pt-24 pb-16 space-y-10">
      <header className="space-y-3">
        <h1 className="text-[14px] font-medium text-zinc-900 dark:text-zinc-100">Connect your agent</h1>
        <p className="text-xs text-zinc-500">
          Use ReachAI from Claude, ChatGPT, Codex, Cursor or any MCP agent. Copy, paste into your agent, done.
        </p>
        <OnboardAgent origin={origin} />
        <p className="text-[11px] text-zinc-500">
          It finds creators, drafts first messages and checks replies. It never sends messages or spends money
          without you.{" "}
          <Link href="/docs/mcp" className="underline underline-offset-2">
            Docs
          </Link>
        </p>
      </header>

      <details className="group rounded-lg border border-zinc-200 dark:border-zinc-800">
        <summary className="cursor-pointer list-none flex items-center justify-between px-4 h-10 text-xs font-medium text-zinc-900 dark:text-zinc-100">
          Set up by hand
          <span className="text-zinc-400 transition-transform group-open:rotate-180">⌄</span>
        </summary>
        <div className="px-4 pb-4 space-y-3">
          <div className="flex items-center gap-2">
            <Input readOnly value={mcpUrl} aria-label="ReachAI MCP address" className="font-mono text-xs" />
            <CopyButton text={mcpUrl} />
          </div>
          <p className="text-[11px] text-zinc-500">
            Claude and ChatGPT: add it as a custom connector and sign in. No key needed.
          </p>
          <Snippet title="Claude Code" code={`claude mcp add --transport http reachai ${mcpUrl}`} />
          <Snippet
            title="Cursor (mcp.json), with a key"
            code={JSON.stringify(
              { mcpServers: { reachai: { url: mcpUrl, headers: { Authorization: `Bearer ${keyForSnippets}` } } } },
              null,
              2,
            )}
          />
        </div>
      </details>

      <section className="space-y-3">
        <div className="space-y-1">
          <h2 className="text-xs font-medium text-zinc-900 dark:text-zinc-100">API keys</h2>
          <p className="text-[11px] text-zinc-500">Only for agents that can&apos;t sign in. Your agent will tell you if it needs one.</p>
        </div>

        {newKey && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 p-3 space-y-2">
            <p className="text-xs font-medium text-amber-900 dark:text-amber-200">
              Copy your new key now. It is shown only once.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs break-all font-mono">{newKey.key}</code>
              <CopyButton text={newKey.key} label="Copy key" />
            </div>
          </div>
        )}

        <div className="flex items-center gap-2">
          <Input
            value={name}
            maxLength={60}
            placeholder="Name, e.g. Claude Code on my laptop"
            aria-label="Key name"
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createKey()}
          />
          <Button type="button" onClick={createKey} disabled={creating || !name.trim()}>
            {creating ? <Loader2 className="size-4 animate-spin" /> : <KeyRound className="size-4" />}
            Create key
          </Button>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}

        {loading ? (
          <p className="text-xs text-neutral-500">Loading…</p>
        ) : keys.length === 0 ? (
          <p className="text-xs text-neutral-500">No keys yet.</p>
        ) : (
          <ul className="divide-y divide-neutral-200 dark:divide-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-800">
            {keys.map((k) => (
              <li key={k.key_id} className="flex items-center justify-between gap-3 px-3 py-2">
                <div className="min-w-0">
                  <p className="text-sm text-neutral-900 dark:text-neutral-100 truncate">{k.name}</p>
                  <p className="text-xs text-neutral-500">
                    <span className="font-mono">{k.prefix}…</span> · Created {formatDate(k.created_at)} · Last used{" "}
                    {formatDate(k.last_used_at)}
                  </p>
                </div>
                <Button type="button" variant="ghost" size="sm" onClick={() => revokeKey(k)} aria-label={`Revoke ${k.name}`}>
                  <Trash2 className="size-3.5" />
                  Revoke
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
