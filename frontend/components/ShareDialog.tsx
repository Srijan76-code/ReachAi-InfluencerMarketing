"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Globe, Link2, Lock, Share2, Trash2, UserPlus } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { updatedLabel } from "@/types/campaign";
import { Segmented } from "@/components/ui/segmented";

/** Share a campaign's shortlist (roadmap F1.18). Like Drive: add people by email (each gets their own
 *  link) as a Viewer or a Reviewer (👍/👎 and comments), or turn on "anyone with the link" (view only).
 *  Contact details only for a named person who confirms a one-time email code. */

export type ShareLinkRow = {
  id: string;
  kind: "person" | "anyone";
  email: string | null;
  role: string;
  show_prices: boolean;
  show_contacts: boolean;
  creator_ids: string[] | null;
  path: string;
  expires_at: string | null;
  view_count: number;
  last_viewed_at: string | null;
};

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;

function errorText(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function daysLeft(iso: string | null): string {
  if (!iso) return "";
  const d = Math.ceil((Date.parse(iso) - Date.now()) / 86_400_000);
  return d <= 1 ? "expires today" : `expires in ${d} days`;
}

function CopyButton({ path }: { path: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(`${window.location.origin}${path}`);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          window.prompt("Copy this link", `${window.location.origin}${path}`);
        }
      }}
      className="flex items-center gap-1 px-2 py-1 rounded-md border border-zinc-200 dark:border-zinc-800 text-[11px] font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800"
    >
      {done ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
      {done ? "Copied" : "Copy link"}
    </button>
  );
}

function Toggle({ checked, onChange, disabled, label, title }: { checked: boolean; onChange?: (v: boolean) => void; disabled?: boolean; label: string; title?: string }) {
  return (
    <label className={`flex items-center gap-1.5 text-[11px] ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`} title={title}>
      <input type="checkbox" className="accent-zinc-900 dark:accent-zinc-100" checked={checked} disabled={disabled} onChange={(e) => onChange?.(e.target.checked)} />
      {label}
    </label>
  );
}

/** One "what to share" option. `ids: null` means the whole shortlist of the campaign, as it is now and later. */
export type ShareScope = { key: string; label: string; ids: string[] | null; count?: number };

export function ShareDialog({ campaignId, api, scopes }: { campaignId: string; api: Api; scopes: ShareScope[] }) {
  const [open, setOpen] = useState(false);
  const [links, setLinks] = useState<ShareLinkRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const usable = scopes.filter((sc) => sc.ids === null || sc.ids.length > 0);
  const [scopeKey, setScopeKey] = useState<string>(scopes[0]?.key ?? "all");
  const scope = usable.find((sc) => sc.key === scopeKey) ?? usable[0] ?? scopes[0];
  const [email, setEmail] = useState("");
  const [prices, setPrices] = useState(false);
  const [role, setRole] = useState<"viewer" | "reviewer">("viewer");
  const [contacts, setContacts] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    // open on the selection if there is one, else on the view you're in (All or Shortlist)
    const sel = scopes.find((sc) => sc.key === "selected" && sc.ids && sc.ids.length);
    setScopeKey(sel ? sel.key : scopes[0]?.key ?? "all");
    setError(null);
    setLoading(true);
    api(`/api/campaigns/${campaignId}/shares`)
      .then((r) => {
        const d = r.data as { links?: ShareLinkRow[]; email_enabled?: boolean };
        setLinks(Array.isArray(d?.links) ? d.links : []);
        setEmailEnabled(Boolean(d?.email_enabled));
      })
      .catch((e) => setError(errorText(e, "Couldn't load the links.")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [open, campaignId]);

  const creatorIds = scope?.ids ?? null;
  const sameScope = (l: ShareLinkRow) => JSON.stringify(l.creator_ids ?? null) === JSON.stringify(creatorIds);
  const anyone = links.find((l) => l.kind === "anyone" && sameScope(l));
  const people = links.filter((l) => l.kind === "person");

  const upsert = (row: ShareLinkRow) => setLinks((ls) => [...ls.filter((l) => l.id !== row.id), row]);

  const create = async (kind: "person" | "anyone", body: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api(`/api/campaigns/${campaignId}/shares`, { method: "POST", data: { kind, creator_ids: creatorIds, ...body } });
      upsert(r.data as ShareLinkRow);
      return true;
    } catch (e) {
      setError(errorText(e, "Couldn't create the link."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const change = async (l: ShareLinkRow, patch: Partial<Pick<ShareLinkRow, "show_prices" | "role" | "show_contacts">>) => {
    upsert({ ...l, ...patch });
    try {
      upsert((await api(`/api/shares/${l.id}`, { method: "PATCH", data: patch })).data as ShareLinkRow);
    } catch (e) {
      upsert(l);
      setError(errorText(e, "Couldn't change the link."));
    }
  };

  const revoke = async (l: ShareLinkRow) => {
    setLinks((ls) => ls.filter((x) => x.id !== l.id));
    try {
      await api(`/api/shares/${l.id}`, { method: "DELETE" });
    } catch (e) {
      upsert(l);
      setError(errorText(e, "Couldn't turn the link off."));
    }
  };

  const scopeLabel = (l: ShareLinkRow) => (l.creator_ids ? `${l.creator_ids.length} creator${l.creator_ids.length === 1 ? "" : "s"}` : "All creators");
  const seen = (l: ShareLinkRow) => (l.view_count ? `Viewed ${l.view_count}× · ${updatedLabel(l.last_viewed_at || "")}` : "Not opened yet");

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-800 transition-colors">
          <Share2 size={14} />
          Share
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg bg-white dark:bg-[#0c0d0e]">
        <DialogHeader>
          <DialogTitle>Share this shortlist</DialogTitle>
          <DialogDescription>
            People don&apos;t need a ReachAI account. Reviewers can approve or reject each creator. Contact details only
            with your OK, after they confirm a code sent to their email.
          </DialogDescription>
        </DialogHeader>

        {/* what to share */}
        <Segmented
          label="What to share"
          size="sm"
          value={scope?.key ?? ""}
          onChange={setScopeKey}
          options={scopes.map((sc) => ({
            value: sc.key,
            label: sc.label,
            count: sc.ids ? sc.ids.length : sc.count,
            disabled: sc.ids !== null && sc.ids.length === 0,
          }))}
        />
        {scope?.key === "shortlist" && (
          <p className="-mt-2 text-[11px] text-zinc-500">The link shows the creators on your shortlist now. Creators you shortlist later aren&apos;t added.</p>
        )}

        {/* add a person */}
        <form
          className="space-y-2"
          onSubmit={async (e) => {
            e.preventDefault();
            if (await create("person", { email, show_prices: prices, role, show_contacts: contacts })) {
              setEmail("");
              setPrices(false);
              setContacts(false);
            }
          }}
        >
          <div className="flex gap-2">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "viewer" | "reviewer")}
              aria-label="Role"
              title="Reviewers can approve or reject each creator and leave a comment"
              className="px-2 py-1.5 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent text-zinc-700 dark:text-zinc-300"
            >
              <option value="viewer">Viewer</option>
              <option value="reviewer">Reviewer</option>
            </select>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Add people by email"
              aria-label="Email"
              className="flex-1 px-2.5 py-1.5 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent focus:outline-none focus:border-zinc-400"
            />
            <button type="submit" disabled={busy || !email.trim()} className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 disabled:opacity-50">
              <UserPlus size={13} /> Add
            </button>
          </div>
          <div className="flex items-center gap-4">
            <Toggle checked={prices} onChange={setPrices} label="Show fair prices" title="Turn off when sharing with a client or a creator's manager" />
            <Toggle
              checked={contacts}
              disabled={!emailEnabled}
              onChange={setContacts}
              label="Show contact details"
              title={emailEnabled ? "They confirm a code sent to their email first" : "Needs email set up (coming soon)"}
            />
          </div>
          <p className="text-[11px] text-zinc-500">Each person gets their own link. Send it to them yourself; we only email them a code if you share contact details.</p>
        </form>

        {error && <p className="text-xs text-rose-500">{error}</p>}

        {/* people with access */}
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">People with access</p>
          {loading ? (
            <p className="text-xs text-zinc-500">Loading…</p>
          ) : people.length === 0 ? (
            <p className="text-xs text-zinc-500">Only you.</p>
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {people.map((l) => (
                <li key={l.id} className="py-2 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100 truncate">{l.email}</p>
                    <p className="text-[10px] text-zinc-500 flex items-center gap-1">
                      <select
                        value={l.role}
                        onChange={(e) => change(l, { role: e.target.value })}
                        aria-label={`Role for ${l.email}`}
                        className="bg-transparent text-[10px] text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-800 rounded px-1 py-px"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="reviewer">Reviewer</option>
                      </select>
                      {scopeLabel(l)} · {seen(l)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Toggle checked={l.show_prices} onChange={(v) => change(l, { show_prices: v })} label="Prices" />
                    <Toggle
                      checked={l.show_contacts}
                      disabled={!emailEnabled && !l.show_contacts}
                      onChange={(v) => change(l, { show_contacts: v })}
                      label="Contacts"
                      title={emailEnabled ? "They confirm a code sent to their email before seeing contact details" : "Needs email set up"}
                    />
                    <CopyButton path={l.path} />
                    <button type="button" onClick={() => revoke(l)} aria-label={`Remove ${l.email}`} title="Remove access" className="p-1 text-zinc-400 hover:text-rose-500">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* general access */}
        <div className="space-y-2 border-t border-zinc-200 dark:border-zinc-800 pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">General access</p>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2">
              {anyone ? <Globe size={16} className="mt-0.5 text-emerald-500" /> : <Lock size={16} className="mt-0.5 text-zinc-400" />}
              <div>
                <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100">{anyone ? "Anyone with the link" : "Restricted"}</p>
                <p className="text-[10px] text-zinc-500">
                  {anyone ? `${scopeLabel(anyone)} · view only · ${daysLeft(anyone.expires_at)} · ${seen(anyone)}` : "Only the people above can open it."}
                </p>
              </div>
            </div>
            {anyone ? (
              <div className="flex items-center gap-2 shrink-0">
                <Toggle checked={anyone.show_prices} onChange={(v) => change(anyone, { show_prices: v })} label="Prices" />
                <CopyButton path={anyone.path} />
                <button type="button" onClick={() => revoke(anyone)} className="text-[11px] text-rose-500 hover:underline">Turn off</button>
              </div>
            ) : (
              <button type="button" disabled={busy} onClick={() => create("anyone", { show_prices: false })} className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-md border border-zinc-200 dark:border-zinc-800 text-[11px] font-medium hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-50">
                <Link2 size={12} /> Create link
              </button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
