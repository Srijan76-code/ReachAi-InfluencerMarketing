"use client";

import { useEffect, useState } from "react";
import { Check, ChevronDown, Globe, Link2, Lock, MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Segmented } from "@/components/ui/segmented";
import { updatedLabel } from "@/types/campaign";

/** Share a shortlist like a Google Drive file (roadmap F1.18): invite people by email (each gets their
 *  own link) to view or review, or let anyone with the link view it. Contact details are never shared. */

export type ShareLinkRow = {
  id: string;
  kind: "person" | "anyone";
  email: string | null;
  role: string;
  show_prices: boolean;
  creator_ids: string[] | null;
  path: string;
  expires_at: string | null;
  view_count: number;
  last_viewed_at: string | null;
};

/** One "what to share" option. `ids: null` means the campaign's whole list. */
export type ShareScope = { key: string; label: string; ids: string[] | null; count?: number };

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
type Role = "viewer" | "reviewer";

const ROLE_LABEL: Record<Role, string> = { viewer: "Can view", reviewer: "Can review" };
const ITEM = "text-xs cursor-pointer focus:bg-zinc-100 dark:focus:bg-zinc-800";
const MENU = "bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800";

function errorText(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function useCopy() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (path: string) => {
    const url = `${window.location.origin}${path}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(path);
      setTimeout(() => setCopied((c) => (c === path ? null : c)), 1500);
    } catch {
      window.prompt("Copy this link", url);
    }
  };
  return { copied, copy };
}

function RoleMenu({ value, onChange }: { value: Role; onChange: (r: Role) => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="flex items-center gap-1 h-8 px-2 rounded-md text-xs text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 whitespace-nowrap">
          {ROLE_LABEL[value]} <ChevronDown size={12} className="opacity-60" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className={`w-52 ${MENU}`}>
        <DropdownMenuRadioGroup value={value} onValueChange={(v) => onChange(v as Role)}>
          <DropdownMenuRadioItem value="viewer" className={ITEM}>
            <div><p>Can view</p><p className="text-[11px] text-zinc-500">See creators and compare them</p></div>
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="reviewer" className={ITEM}>
            <div><p>Can review</p><p className="text-[11px] text-zinc-500">Also approve, reject and comment</p></div>
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function CopyIcon({ path, copied, onCopy }: { path: string; copied: boolean; onCopy: () => void }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" onClick={onCopy} aria-label="Copy link" className="h-8 w-8 flex items-center justify-center rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800">
          {copied ? <Check size={14} className="text-emerald-500" /> : <Link2 size={14} />}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs">{copied ? "Copied" : "Copy link"}</TooltipContent>
    </Tooltip>
  );
}

/** The People tab of the Sharing panel: invite, roles, copy, prices, remove, general access.
 *  `active`: the panel is open (load and refresh then). `onChanged`: tell the panel something changed. */
export function ShareManager({ campaignId, api, scopes, active, onChanged }: {
  campaignId: string;
  api: Api;
  scopes: ShareScope[];
  active: boolean;
  onChanged?: () => void;
}) {
  const open = active;
  const [links, setLinks] = useState<ShareLinkRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [busy, setBusy] = useState(false);
  const { copied, copy } = useCopy();

  const usable = scopes.filter((sc) => sc.ids === null || sc.ids.length > 0);
  const [scopeKey, setScopeKey] = useState<string>(scopes[0]?.key ?? "all");
  const scope = usable.find((sc) => sc.key === scopeKey) ?? usable[0] ?? scopes[0];
  const creatorIds = scope?.ids ?? null;

  useEffect(() => {
    if (!open) return;
    const sel = scopes.find((sc) => sc.key === "selected" && sc.ids && sc.ids.length);
    setScopeKey(sel ? sel.key : scopes[0]?.key ?? "all");
    setError(null);
    setLoading(true);
    api(`/api/campaigns/${campaignId}/shares`)
      .then((r) => {
        const d = r.data as { links?: ShareLinkRow[] };
        setLinks(Array.isArray(d?.links) ? d.links : []);
      })
      .catch((e) => setError(errorText(e, "Couldn't load who has access.")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- api changes every render
  }, [open, campaignId]);

  const sameScope = (l: ShareLinkRow) => JSON.stringify(l.creator_ids ?? null) === JSON.stringify(creatorIds);
  const anyone = links.find((l) => l.kind === "anyone" && sameScope(l));
  const people = links.filter((l) => l.kind === "person");
  const upsert = (row: ShareLinkRow) => {
    setLinks((ls) => [...ls.filter((l) => l.id !== row.id), row]);
    onChanged?.();
  };

  const create = async (kind: "person" | "anyone", body: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      const r = await api(`/api/campaigns/${campaignId}/shares`, { method: "POST", data: { kind, creator_ids: creatorIds, ...body } });
      upsert(r.data as ShareLinkRow);
      return r.data as ShareLinkRow;
    } catch (e) {
      setError(errorText(e, "Couldn't share. Try again."));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const change = async (l: ShareLinkRow, patch: Partial<Pick<ShareLinkRow, "show_prices" | "role">>) => {
    upsert({ ...l, ...patch });
    try {
      upsert((await api(`/api/shares/${l.id}`, { method: "PATCH", data: patch })).data as ShareLinkRow);
    } catch (e) {
      upsert(l);
      setError(errorText(e, "Couldn't save that change."));
    }
  };

  const revoke = async (l: ShareLinkRow) => {
    setLinks((ls) => ls.filter((x) => x.id !== l.id));
    try {
      await api(`/api/shares/${l.id}`, { method: "DELETE" });
    } catch (e) {
      upsert(l);
      setError(errorText(e, "Couldn't remove access."));
    }
  };

  const invite = async () => {
    const row = await create("person", { email, role, show_prices: false });
    if (row) {
      setEmail("");
      copy(row.path); // the new link is ready to paste
    }
  };

  const seen = (l: ShareLinkRow) => (l.view_count ? `Opened ${updatedLabel(l.last_viewed_at || "")}` : "Not opened yet");
  const daysLeft = (iso: string | null) => (iso ? Math.max(0, Math.ceil((Date.parse(iso) - Date.now()) / 86_400_000)) : 0);

  return (
    <div className="space-y-5">

        {usable.length > 1 && (
          <Segmented
            label="What to share"
            size="sm"
            value={scope?.key ?? ""}
            onChange={setScopeKey}
            options={scopes.map((sc) => ({ value: sc.key, label: sc.label, count: sc.ids ? sc.ids.length : sc.count, disabled: sc.ids !== null && sc.ids.length === 0 }))}
          />
        )}

        {/* invite */}
        <form
          className="flex items-center gap-1.5 rounded-md border border-zinc-200 dark:border-zinc-800 pl-2.5 pr-1 focus-within:border-zinc-400 dark:focus-within:border-zinc-600"
          onSubmit={(e) => {
            e.preventDefault();
            invite();
          }}
        >
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Add people by email"
            aria-label="Email"
            className="flex-1 min-w-0 h-9 text-sm bg-transparent focus:outline-none placeholder:text-zinc-400"
          />
          <RoleMenu value={role} onChange={setRole} />
          <button type="submit" disabled={busy || !email.trim()} className="h-7 px-3 text-xs font-medium rounded-md bg-zinc-900 text-white dark:bg-zinc-300 dark:text-zinc-900 hover:opacity-90 disabled:opacity-40">
            Invite
          </button>
        </form>

        {error && <p className="-mt-2 text-xs text-rose-500">{error}</p>}

        {/* people */}
        {(loading || people.length > 0) && (
          <ul className="-mx-1 space-y-0.5">
            {loading ? (
              <li className="px-1 text-xs text-zinc-500">Loading…</li>
            ) : (
              people.map((l) => (
                <li key={l.id} className="flex items-center gap-2.5 px-1 py-1 rounded-md">
                  <span className="h-7 w-7 shrink-0 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-[11px] font-medium text-zinc-700 dark:text-zinc-300 uppercase">
                    {(l.email || "?").charAt(0)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] text-zinc-900 dark:text-zinc-100 truncate">{l.email}</p>
                    <p className="text-[11px] text-zinc-500 truncate">
                      {seen(l)}
                      {l.show_prices && " · sees prices"}
                    </p>
                  </div>
                  <RoleMenu value={(l.role as Role) || "viewer"} onChange={(r) => change(l, { role: r })} />
                  <CopyIcon path={l.path} copied={copied === l.path} onCopy={() => copy(l.path)} />
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button type="button" aria-label={`More for ${l.email}`} className="h-8 w-8 flex items-center justify-center rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800">
                        <MoreHorizontal size={14} />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className={`w-44 ${MENU}`}>
                      <DropdownMenuCheckboxItem className={ITEM} checked={l.show_prices} onCheckedChange={(v) => change(l, { show_prices: v === true })}>
                        Show prices
                      </DropdownMenuCheckboxItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className={`${ITEM} text-rose-500 focus:text-rose-500`} onSelect={() => revoke(l)}>
                        Remove access
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              ))
            )}
          </ul>
        )}

        {/* general access */}
        <div className="flex items-center gap-2.5 border-t border-zinc-100 dark:border-zinc-900 pt-4">
          <span className={`h-7 w-7 shrink-0 rounded-full flex items-center justify-center ${anyone ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-zinc-100 dark:bg-zinc-800 text-zinc-500"}`}>
            {anyone ? <Globe size={14} /> : <Lock size={14} />}
          </span>
          <div className="min-w-0 flex-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" disabled={busy} className="flex items-center gap-1 text-[13px] font-medium text-zinc-900 dark:text-zinc-100 hover:underline underline-offset-2">
                  {anyone ? "Anyone with the link" : "Restricted"} <ChevronDown size={12} className="opacity-60" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className={`w-60 ${MENU}`}>
                <DropdownMenuRadioGroup
                  value={anyone ? "anyone" : "restricted"}
                  onValueChange={(v) => {
                    if (v === "anyone" && !anyone) create("anyone", { show_prices: false });
                    if (v === "restricted" && anyone) revoke(anyone);
                  }}
                >
                  <DropdownMenuRadioItem value="restricted" className={ITEM}>
                    <div><p>Restricted</p><p className="text-[11px] text-zinc-500">Only people you add</p></div>
                  </DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="anyone" className={ITEM}>
                    <div><p>Anyone with the link</p><p className="text-[11px] text-zinc-500">View only, for 30 days</p></div>
                  </DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
                {anyone && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuCheckboxItem className={ITEM} checked={anyone.show_prices} onCheckedChange={(v) => change(anyone, { show_prices: v === true })}>
                      Show prices
                    </DropdownMenuCheckboxItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            <p className="text-[11px] text-zinc-500 truncate">
              {anyone
                ? `View only · ${daysLeft(anyone.expires_at)} days left · ${seen(anyone).toLowerCase()}`
                : "Only people you add can open it"}
            </p>
          </div>
          {anyone && (
            <button
              type="button"
              onClick={() => copy(anyone.path)}
              className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            >
              {copied === anyone.path ? <Check size={13} className="text-emerald-500" /> : <Link2 size={13} />}
              {copied === anyone.path ? "Copied" : "Copy link"}
            </button>
          )}
        </div>
    </div>
  );
}
