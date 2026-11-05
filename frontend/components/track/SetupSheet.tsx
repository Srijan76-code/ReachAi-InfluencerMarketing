"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, CheckCircle2, Copy, Download, ExternalLink, FileUp, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { btn, btnPrimary, control } from "@/lib/ui";
import type { Track } from "@/data/track";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
type Snip = Track["snippet"];
type Block = { label?: string; code: string; file?: string };
type Platform = { id: string; name: string; group: "code" | "builder" | "other"; steps: (s: Snip) => (string | Block)[] };

const tag = (s: Snip, extra = "") => `<script src="${s.src}" data-key="${s.key}"${extra} async></script>`;

/** Every way to count signups, from "I code in Next.js" to "I use Wix". Each gives the exact steps and
 * a copy-paste block with the founder's key filled in. */
const PLATFORMS: Platform[] = [
  {
    id: "nextjs", name: "Next.js", group: "code",
    steps: (s) => [
      "1. Add this file",
      { file: "components/ReachAI.tsx", code: `"use client";\nimport Script from "next/script";\n\n/** Counts signups from creators' ReachAI links. Put <ReachAI /> once in app/layout.tsx. */\nexport function ReachAI() {\n  return <Script src="${s.src}" data-key="${s.key}" strategy="afterInteractive" />;\n}\n\n/** Call this right after someone signs up. */\nexport function reachaiSignup() {\n  (window as unknown as { reachai?: (kind: string) => void }).reachai?.("signup");\n}\n` },
      "2. Add it to app/layout.tsx, inside <body>",
      { code: `import { ReachAI } from "@/components/ReachAI";\n\n// inside <body>\n<ReachAI />` },
      "3. Call it after a signup",
      { code: `import { reachaiSignup } from "@/components/ReachAI";\n\nreachaiSignup();` },
    ],
  },
  {
    id: "react", name: "React (Vite, CRA)", group: "code",
    steps: (s) => [
      "1. Add this file",
      { file: "src/reachai.ts", code: `/** Counts signups from creators' ReachAI links. Call loadReachAI() once when your app starts. */\nexport function loadReachAI() {\n  if (document.querySelector("script[data-reachai]")) return;\n  const s = document.createElement("script");\n  s.src = "${s.src}";\n  s.async = true;\n  s.dataset.key = "${s.key}";\n  s.dataset.reachai = "";\n  document.head.appendChild(s);\n}\n\n/** Call this right after someone signs up. */\nexport function reachaiSignup() {\n  (window as unknown as { reachai?: (kind: string) => void }).reachai?.("signup");\n}\n` },
      "2. Load it in src/main.tsx",
      { code: `import { loadReachAI } from "./reachai";\n\nloadReachAI();` },
      "3. Call it after a signup",
      { code: `import { reachaiSignup } from "./reachai";\n\nreachaiSignup();` },
    ],
  },
  {
    id: "html", name: "HTML / other code", group: "code",
    steps: (s) => [
      "1. Every page, inside <head>",
      { code: tag(s) },
      "2. Your thank-you page, instead",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "server", name: "Your server (any language)", group: "code",
    steps: (s) => [
      "1. Save the ?ref= value from the landing URL with the user",
      "2. After signup, send",
      { label: "curl", code: `curl -X POST ${s.endpoint} \\\n  -H "Content-Type: application/json" \\\n  -d '{"ref": "SRIJAN42", "kind": "signup"}'` },
      { label: "Node / Next.js", code: `await fetch("${s.endpoint}", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({ ref: user.ref, kind: "signup" }), // or "sale"\n});` },
      { label: "Python", code: `import requests\n\nrequests.post("${s.endpoint}", json={"ref": user.ref, "kind": "signup"}, timeout=5)` },
    ],
  },
  {
    id: "webflow", name: "Webflow", group: "builder",
    steps: (s) => [
      "1. Site settings → Custom code → Head code",
      { code: tag(s) },
      "2. Thank-you page → Page settings → Custom code → Before </body>",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "framer", name: "Framer", group: "builder",
    steps: (s) => [
      "1. Site settings → General → Custom code → End of <head>",
      { code: tag(s) },
      "2. Thank-you page → Page settings → Custom code → End of <body>",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "wordpress", name: "WordPress", group: "builder",
    steps: (s) => [
      "1. Install WPCode → Header & Footer → Header",
      { code: tag(s) },
      "2. Thank-you page → Custom HTML block",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "wix", name: "Wix", group: "builder",
    steps: (s) => [
      "1. Settings → Custom code → All pages, Head",
      { code: tag(s) },
      "2. Custom code → Thank-you page only, Body end",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "squarespace", name: "Squarespace", group: "builder",
    steps: (s) => [
      "1. Settings → Advanced → Code injection → Header",
      { code: tag(s) },
      "2. Thank-you page → Advanced → Page header code injection",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "ai", name: "Lovable, Bolt, v0, Replit", group: "builder",
    steps: (s) => [
      "Paste this into the chat",
      { code: `Add ReachAI signup tracking:\n1. Load this script on every page (in the HTML head or root layout): ${tag(s)}\n2. Right after a user signs up successfully, run: window.reachai && window.reachai("signup")\nDon't change anything else.` },
    ],
  },
  {
    id: "gtm", name: "Google Tag Manager", group: "builder",
    steps: (s) => [
      "1. Custom HTML tag · All Pages",
      { code: tag(s) },
      "2. Custom HTML tag · your signup event",
      { code: `<script>window.reachai && window.reachai("signup");</script>` },
    ],
  },
  {
    id: "shopify", name: "Shopify", group: "other",
    steps: (s) => [
      "Analytics → Reports → Sales by discount → Export, then upload it",
    ],
  },
  { id: "store", name: "Stripe or another store", group: "other", steps: () => [] },
  {
    id: "hand", name: "I'll add numbers myself", group: "other",
    steps: () => ["Creators → ⋯ → Add signups"],
  },
];

function CodeBlock({ b }: { b: Block }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(b.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([b.code], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = b.file!.split("/").pop()!;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden min-w-0 max-w-full">
      {(b.file || b.label) && <p className="px-3 py-1.5 text-[10px] font-mono text-zinc-500 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-[#101112]">{b.file ?? b.label}</p>}
      <pre className="text-[11px] leading-relaxed bg-zinc-50 dark:bg-[#121314] px-3 py-2.5 overflow-x-auto whitespace-pre text-zinc-800 dark:text-zinc-200 max-h-64">{b.code}</pre>
      <div className="flex gap-1.5 px-2 py-1.5 bg-zinc-50 dark:bg-[#101112] border-t border-zinc-200 dark:border-zinc-800">
        <button type="button" onClick={copy} className={btn}>{copied ? <Check size={12} /> : <Copy size={12} />} {copied ? "Copied" : "Copy"}</button>
        {b.file && <button type="button" onClick={download} className={btn}><Download size={12} /> Download</button>}
      </div>
    </div>
  );
}

/** Store export (Shopify, Stripe…): a CSV file of codes and how often each was used. */
function StoreUpload({ api, campaignId, onDone }: { api: Api; campaignId: string; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const pick = async (f: File | undefined) => {
    if (!f) return;
    setBusy(true);
    setNote(null);
    try {
      const text = await f.text();
      const r = (await api(`/api/campaigns/${campaignId}/conversions/csv`, { method: "POST", data: { text, kind: "code_use" } })).data as { added: number; unknown_codes: string[] };
      setNote(`Added ${r.added} code uses${r.unknown_codes.length ? ` · skipped ${r.unknown_codes.join(", ")}` : ""}`);
      onDone();
    } catch {
      setNote("Couldn't read that file");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500">A CSV of each discount code and its uses.</p>
      <label className={`${btn} cursor-pointer w-fit`}>
        {busy ? <Loader2 size={12} className="animate-spin" /> : <FileUp size={12} />} Upload CSV
        <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
      </label>
      {note && <p className="text-[11px] text-zinc-500">{note}</p>}
    </div>
  );
}

/** "Test it": opens the founder's site in test mode; the snippet reports in and this turns green. */
function Tester({ snippet, api, campaignId, onSeen }: { snippet: Snip; api: Api; campaignId: string; onSeen: () => void }) {
  const [site, setSite] = useState(snippet.site ?? "");
  const [state, setState] = useState<"idle" | "waiting" | "ok" | "timeout">(snippet.seen_at ? "ok" : "idle");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => () => {
    if (timer.current) clearInterval(timer.current);
  }, []);
  const test = () => {
    let url = site.trim();
    if (!url) return;
    if (!/^https?:\/\//.test(url)) url = "https://" + url;
    const u = new URL(url);
    u.searchParams.set("reachai_test", "1");
    window.open(u.toString(), "_blank", "noopener,noreferrer");
    const before = snippet.seen_at;
    setState("waiting");
    let tries = 0;
    timer.current = setInterval(async () => {
      tries += 1;
      try {
        const t = (await api(`/api/campaigns/${campaignId}/track`)).data as Track;
        if (t.snippet.seen_at && t.snippet.seen_at !== before) {
          clearInterval(timer.current!);
          setState("ok");
          onSeen();
          return;
        }
      } catch {}
      if (tries >= 20) {
        clearInterval(timer.current!);
        setState("timeout");
      }
    }, 3000);
  };
  return (
    <div className="space-y-1.5 pt-1">
      <div className="flex gap-2">
        <input value={site} onChange={(e) => setSite(e.target.value)} placeholder="yoursite.com" aria-label="Your site" className={control} />
        <button type="button" onClick={test} disabled={!site.trim() || state === "waiting"} className={btnPrimary}>
          {state === "waiting" ? <Loader2 size={12} className="animate-spin" /> : <ExternalLink size={12} />} Test
        </button>
      </div>
      <AnimatePresence mode="wait">
        <motion.p key={state} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className={`text-[11px] flex items-center gap-1.5 ${state === "ok" ? "text-emerald-600 dark:text-emerald-400" : state === "timeout" ? "text-rose-500" : "text-zinc-500"}`}>
          {state === "ok" ? <><CheckCircle2 size={12} /> Working</>
            : state === "waiting" ? "Checking…"
            : state === "timeout" ? "Not found yet. Publish your site and try again"
            : "Test once it's on your site"}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

export function SetupSheet({ open, onOpenChange, track, api, campaignId, onChanged }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  track: Track;
  api: Api;
  campaignId: string;
  onChanged: () => void;
}) {
  const [pick, setPick] = useState("nextjs");
  const p = PLATFORMS.find((x) => x.id === pick)!;
  const s = track.snippet;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto overflow-x-hidden bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 gap-4 [&>*]:min-w-0">
        <DialogHeader className="space-y-1">
          <DialogTitle className="text-[14px] font-medium flex items-center gap-2">
            Count signups
            {s.seen_at && <span className="text-[11px] font-normal text-emerald-600 dark:text-emerald-400 flex items-center gap-1"><CheckCircle2 size={12} /> Working</span>}
          </DialogTitle>
          <DialogDescription className="text-xs">Add this to your site once.</DialogDescription>
        </DialogHeader>
        <Field label="Your site is built with">
          <Select label="Your site is built with" value={pick} onChange={setPick} options={PLATFORMS.map((x) => ({ value: x.id, label: x.name }))} />
        </Field>
        <AnimatePresence mode="wait">
          <motion.div key={p.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="space-y-2.5 min-w-0">
            {p.id === "store" ? <StoreUpload api={api} campaignId={campaignId} onDone={onChanged} /> : p.steps(s).map((st, i) =>
              typeof st === "string" ? <p key={i} className="text-xs text-zinc-600 dark:text-zinc-400">{st}</p> : <CodeBlock key={i} b={st} />)}
            {p.id === "shopify" && <StoreUpload api={api} campaignId={campaignId} onDone={onChanged} />}
            {!["store", "hand", "server", "shopify"].includes(p.id) && <Tester snippet={s} api={api} campaignId={campaignId} onSeen={onChanged} />}
          </motion.div>
        </AnimatePresence>
      </DialogContent>
    </Dialog>
  );
}
