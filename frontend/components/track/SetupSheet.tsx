"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, CheckCircle2, Copy, Download, ExternalLink, FileUp, Loader2 } from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { btn, btnPrimary, control } from "@/lib/ui";
import type { Track } from "@/data/track";
import { updatedLabel } from "@/types/campaign";

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
      "Add this file to your project (or download it):",
      { file: "components/ReachAI.tsx", code: `"use client";\nimport Script from "next/script";\n\n/** Counts signups from creators' ReachAI links. Put <ReachAI /> once in app/layout.tsx. */\nexport function ReachAI() {\n  return <Script src="${s.src}" data-key="${s.key}" strategy="afterInteractive" />;\n}\n\n/** Call this right after someone signs up. */\nexport function reachaiSignup() {\n  (window as unknown as { reachai?: (kind: string) => void }).reachai?.("signup");\n}\n` },
      "In app/layout.tsx, import it and put it inside <body>:",
      { code: `import { ReachAI } from "@/components/ReachAI";\n\n// inside <body>\n<ReachAI />` },
      "Where your signup succeeds (or on your welcome page), call:",
      { code: `import { reachaiSignup } from "@/components/ReachAI";\n\nreachaiSignup();` },
    ],
  },
  {
    id: "react", name: "React (Vite, CRA)", group: "code",
    steps: (s) => [
      "Add this file to your project (or download it):",
      { file: "src/reachai.ts", code: `/** Counts signups from creators' ReachAI links. Call loadReachAI() once when your app starts. */\nexport function loadReachAI() {\n  if (document.querySelector("script[data-reachai]")) return;\n  const s = document.createElement("script");\n  s.src = "${s.src}";\n  s.async = true;\n  s.dataset.key = "${s.key}";\n  s.dataset.reachai = "";\n  document.head.appendChild(s);\n}\n\n/** Call this right after someone signs up. */\nexport function reachaiSignup() {\n  (window as unknown as { reachai?: (kind: string) => void }).reachai?.("signup");\n}\n` },
      "In src/main.tsx (or index.tsx), before rendering:",
      { code: `import { loadReachAI } from "./reachai";\n\nloadReachAI();` },
      "Where your signup succeeds, call:",
      { code: `import { reachaiSignup } from "./reachai";\n\nreachaiSignup();` },
    ],
  },
  {
    id: "html", name: "HTML / other code", group: "code",
    steps: (s) => [
      "Paste this inside <head> on every page:",
      { code: tag(s) },
      "On the page people see after signing up, use this line instead:",
      { code: tag(s, " data-signup") },
      "Single-page app? Load the first line once and call window.reachai(\"signup\") when a signup succeeds.",
    ],
  },
  {
    id: "server", name: "Your server (any language)", group: "code",
    steps: (s) => [
      "Best for developers: works with ad blockers and when people finish signing up on another device.",
      "1. When someone lands on your site, read ref from the address (yoursite.com?ref=SRIJAN42) and keep it with their account (or in a cookie).",
      "2. After they sign up, send one request from your server:",
      { label: "curl", code: `curl -X POST ${s.endpoint} \\\n  -H "Content-Type: application/json" \\\n  -d '{"ref": "SRIJAN42", "kind": "signup"}'` },
      { label: "Node / Next.js", code: `await fetch("${s.endpoint}", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({ ref: user.ref, kind: "signup" }), // or "sale"\n});` },
      { label: "Python", code: `import requests\n\nrequests.post("${s.endpoint}", json={"ref": user.ref, "kind": "signup"}, timeout=5)` },
    ],
  },
  {
    id: "webflow", name: "Webflow", group: "builder",
    steps: (s) => [
      "1. Site settings → Custom code → Head code: paste this, then Save.",
      { code: tag(s) },
      "2. Open your thank-you page → Page settings (gear) → Custom code → Before </body> tag: paste this.",
      { code: tag(s, " data-signup") },
      "3. Publish.",
    ],
  },
  {
    id: "framer", name: "Framer", group: "builder",
    steps: (s) => [
      "1. Site settings → General → Custom code → End of <head> tag: paste this.",
      { code: tag(s) },
      "2. Open your thank-you page → page settings → Custom code → End of <body> tag: paste this.",
      { code: tag(s, " data-signup") },
      "3. Publish.",
    ],
  },
  {
    id: "wordpress", name: "WordPress", group: "builder",
    steps: (s) => [
      "1. Install the free WPCode plugin (Plugins → Add new → \"WPCode\").",
      "2. Code snippets → Header & Footer → Header: paste this, then Save.",
      { code: tag(s) },
      "3. Edit your thank-you page → add a Custom HTML block → paste this, then Update.",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "wix", name: "Wix", group: "builder",
    steps: (s) => [
      "1. Settings → Custom code → Add custom code: paste this, choose All pages, place in Head, Apply.",
      { code: tag(s) },
      "2. Add custom code again: paste this, choose your thank-you page only, place in Body - end.",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "squarespace", name: "Squarespace", group: "builder",
    steps: (s) => [
      "1. Settings → Advanced → Code injection → Header: paste this, then Save.",
      { code: tag(s) },
      "2. Thank-you page → ⚙ → Advanced → Page header code injection: paste this.",
      { code: tag(s, " data-signup") },
    ],
  },
  {
    id: "ai", name: "Lovable, Bolt, v0, Replit", group: "builder",
    steps: (s) => [
      "Paste this message into your AI builder's chat:",
      { code: `Add ReachAI signup tracking:\n1. Load this script on every page (in the HTML head or root layout): ${tag(s)}\n2. Right after a user signs up successfully, run: window.reachai && window.reachai("signup")\nDon't change anything else.` },
      "Then publish your site and press Test below.",
    ],
  },
  {
    id: "gtm", name: "Google Tag Manager", group: "builder",
    steps: (s) => [
      "1. New tag → Custom HTML → paste this → trigger: All Pages.",
      { code: tag(s) },
      "2. New tag → Custom HTML → paste this → trigger: your signup event (or the thank-you page view).",
      { code: `<script>window.reachai && window.reachai("signup");</script>` },
      "3. Submit and publish the container.",
    ],
  },
  {
    id: "shopify", name: "Shopify", group: "other",
    steps: (s) => [
      "For sales, discount codes are the most reliable on Shopify: each creator's code is already theirs.",
      "1. Analytics → Reports → Sales by discount → Export (CSV).",
      "2. Upload that file under Store codes below. Repeat weekly.",
      "Want visits and newsletter signups too? Online Store → Themes → ⋯ → Edit code → theme.liquid, just before </head>:",
      { code: tag(s) },
    ],
  },
  { id: "store", name: "Stripe or another store (codes)", group: "other", steps: () => [] },
  {
    id: "hand", name: "I'll enter numbers myself", group: "other",
    steps: () => ["In Track → Creators, use ⋯ on a creator → Add signups or code uses. Use it for numbers from any dashboard."],
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
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
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
      setNote(`Added ${r.added} code uses.${r.unknown_codes.length ? ` Codes that aren't your creators': ${r.unknown_codes.join(", ")}.` : ""}`);
      onDone();
    } catch {
      setNote("Couldn't read that file. It needs a code and a number of uses on each row.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-600 dark:text-zinc-400">Export how many times each discount code was used (Stripe: Products → Coupons → export; most stores have a &ldquo;sales by discount&rdquo; report), then upload it. Each code is matched to its creator.</p>
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
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-3.5 space-y-2.5">
      <p className="text-xs font-medium text-zinc-900 dark:text-zinc-100">Test it</p>
      <div className="flex gap-2">
        <input value={site} onChange={(e) => setSite(e.target.value)} placeholder="yoursite.com" aria-label="Your site" className={control} />
        <button type="button" onClick={test} disabled={!site.trim() || state === "waiting"} className={btnPrimary}>
          {state === "waiting" ? <Loader2 size={12} className="animate-spin" /> : <ExternalLink size={12} />} Open my site
        </button>
      </div>
      <AnimatePresence mode="wait">
        <motion.p key={state} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className={`text-[11px] flex items-center gap-1.5 ${state === "ok" ? "text-emerald-600 dark:text-emerald-400" : state === "timeout" ? "text-rose-500" : "text-zinc-500"}`}>
          {state === "ok" ? <><CheckCircle2 size={12} /> Working. ReachAI can see your site.</>
            : state === "waiting" ? "Waiting for your site to report in… (keep the new tab open for a few seconds)"
            : state === "timeout" ? "Didn't hear from your site. Check the code is on the page and the site is published, then try again."
            : "Opens your site in a new tab. If the code is in place, this turns green."}
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
  const [pick, setPick] = useState<string | null>(null);
  const p = PLATFORMS.find((x) => x.id === pick);
  const s = track.snippet;
  const groups: [Platform["group"], string][] = [["code", "I code it"], ["builder", "Website builder"], ["other", "Store or by hand"]];
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-xl bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 p-0 gap-0">
        <SheetHeader className="px-5 pt-5 pb-4 border-b border-zinc-200/70 dark:border-zinc-800/70">
          <SheetTitle className="text-[14px] font-medium">Count signups from creators</SheetTitle>
          <SheetDescription className="text-xs">
            Clicks are counted already. To see who <b>signed up or bought</b>, ReachAI needs one small piece on your site. It only sends the creator&apos;s code, nothing about the person.
          </SheetDescription>
          <p className={`mt-2 text-[11px] flex items-center gap-1.5 ${s.seen_at ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-500"}`}>
            {s.seen_at ? <><CheckCircle2 size={12} /> Set up{s.last_conversion_at ? `, last result ${updatedLabel(s.last_conversion_at)}` : ", no results yet"}</> : "Not set up yet"}
          </p>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          <div className="space-y-3">
            <p className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">What&apos;s your site built with?</p>
            {groups.map(([g, label]) => (
              <div key={g} className="space-y-1.5">
                <p className="text-[11px] text-zinc-500">{label}</p>
                <div className="flex flex-wrap gap-1.5">
                  {PLATFORMS.filter((x) => x.group === g).map((x) => (
                    <button key={x.id} type="button" onClick={() => setPick(x.id)} aria-pressed={pick === x.id}
                      className={`h-8 px-3 rounded-full border text-xs transition-colors ${pick === x.id ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900" : "border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}>
                      {x.name}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {p && (
              <motion.div key={p.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3 border-t border-zinc-200/70 dark:border-zinc-800/70 pt-4">
                <p className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">{p.name}</p>
                {p.id === "store" ? <StoreUpload api={api} campaignId={campaignId} onDone={onChanged} /> : p.steps(s).map((st, i) =>
                  typeof st === "string" ? <p key={i} className="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed">{st}</p> : <CodeBlock key={i} b={st} />)}
                {p.id === "shopify" && <StoreUpload api={api} campaignId={campaignId} onDone={onChanged} />}
                {!["store", "hand", "server"].includes(p.id) && <Tester snippet={s} api={api} campaignId={campaignId} onSeen={onChanged} />}
              </motion.div>
            )}
          </AnimatePresence>

          <details className="text-[11px] text-zinc-500">
            <summary className="cursor-pointer">How it works</summary>
            <p className="mt-2 leading-relaxed">Each creator&apos;s link sends people to your site as yoursite.com?ref=THEIRCODE. The script remembers that code for 30 days in the visitor&apos;s browser on your site. When they sign up, it tells ReachAI &ldquo;one signup for THEIRCODE&rdquo;. We count the last creator link someone came through, or the code they typed at checkout.</p>
          </details>
        </div>
      </SheetContent>
    </Sheet>
  );
}
