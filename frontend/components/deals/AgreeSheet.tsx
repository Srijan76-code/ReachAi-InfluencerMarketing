"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Link2, Loader2, Plus, X } from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { btn, btnPrimary, control } from "@/lib/ui";
import { type Deal, DELIVERABLES, PAY_WHEN, type Proposal } from "@/data/deals";

type Api = (url: string, options?: Record<string, unknown>) => Promise<{ data: unknown }>;
type Row = { key: number; deliverable: string; due_on: string };

const inDays = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};

/** Agreeing a deal (roadmap F7.10c): the price, each post with its date, when they're paid and where their
 * tracking link goes. ReachAI makes their link and code and drafts the confirmation message in the chat. */
export function AgreeSheet({ open, onOpenChange, deal, api, website, onDone }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  deal: Deal;
  api: Api;
  website: string | null;
  onDone: (r: { deal: Deal; proposals?: Proposal[] }) => void;
}) {
  const start = deal.agreed_rate ?? deal.quoted_rate ?? null;
  const [fee, setFee] = useState(start != null ? String(start) : "");
  const [pct, setPct] = useState(deal.deal_type !== "flat" && deal.commission_pct ? String(deal.commission_pct) : "");
  const [rows, setRows] = useState<Row[]>(() =>
    deal.posts?.length
      ? deal.posts.map((p, i) => ({ key: i, deliverable: p.deliverable, due_on: p.due_on ?? "" }))
      : [{ key: 0, deliverable: deal.deliverable || "integration", due_on: deal.post_by ?? inDays(14) }]);
  const [payWhen, setPayWhen] = useState(deal.pay_when ?? "on_live");
  const [linkTo, setLinkTo] = useState(deal.link?.target ?? website ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = (await api(`/api/deals/${deal.id}/agree`, {
        method: "POST",
        data: {
          fee: fee.trim() ? Number(fee) : null,
          commission_pct: pct.trim() ? Number(pct) : null,
          posts: rows.map((r) => ({ deliverable: r.deliverable, due_on: r.due_on || null })),
          pay_when: payWhen,
          link_to: linkTo.trim() || null,
        },
      })).data as { deal: Deal; proposals?: Proposal[] };
      onDone(r);
      onOpenChange(false);
    } catch (e) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof d === "string" ? d.replace(/\.$/, "") : "Couldn't save. Try again");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 p-0 gap-0">
        <SheetHeader className="px-5 pt-5 pb-4 border-b border-zinc-200/70 dark:border-zinc-800/70">
          <SheetTitle className="text-[14px] font-medium">{deal.posts?.length ? "Agreed terms" : `Agree with ${deal.name}`}</SheetTitle>
          <SheetDescription className="text-xs">What they&apos;ll post and when. ReachAI writes it up for you to send, with their link and code.</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          <section className="space-y-3">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Price</h3>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Fee">
                <span className="relative">
                  <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400">$</span>
                  <input value={fee} onChange={(e) => setFee(e.target.value.replace(/[^\d.]/g, ""))} inputMode="decimal" placeholder="0" aria-label="Fee" className={`${control} pl-6`} />
                </span>
              </Field>
              <Field label="Commission (optional)">
                <span className="relative">
                  <input value={pct} onChange={(e) => setPct(e.target.value.replace(/[^\d.]/g, ""))} inputMode="decimal" placeholder="0" aria-label="Commission" className={`${control} pr-6`} />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400">%</span>
                </span>
              </Field>
            </div>
            <Field label="They get paid">
              <Select label="They get paid" value={payWhen} onChange={setPayWhen} options={PAY_WHEN.map(([value, label]) => ({ value, label }))} />
            </Field>
          </section>

          <section className="space-y-2">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Posts</h3>
            <ul className="space-y-2">
              <AnimatePresence initial={false}>
                {rows.map((r, i) => (
                  <motion.li key={r.key} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
                    className="grid grid-cols-[minmax(0,1fr)_140px_30px] gap-2 items-center">
                    <Select label={`Post ${i + 1}`} value={r.deliverable} onChange={(v) => setRows((rs) => rs.map((x) => (x.key === r.key ? { ...x, deliverable: v } : x)))}
                      options={DELIVERABLES.map(([value, label]) => ({ value, label }))} />
                    <input type="date" value={r.due_on} aria-label={`Post ${i + 1} due`} onChange={(e) => setRows((rs) => rs.map((x) => (x.key === r.key ? { ...x, due_on: e.target.value } : x)))}
                      className={`${control} [color-scheme:light] dark:[color-scheme:dark]`} />
                    <button type="button" onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))} disabled={rows.length === 1} aria-label={`Remove post ${i + 1}`}
                      className="h-[30px] w-[30px] flex items-center justify-center rounded-md text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-30">
                      <X size={13} />
                    </button>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
            {rows.length < 10 && (
              <button type="button" onClick={() => setRows((rs) => [...rs, { key: Date.now(), deliverable: "short", due_on: rs[rs.length - 1]?.due_on || inDays(14) }])} className={btn}>
                <Plus size={12} /> Add a post
              </button>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Tracking</h3>
            <Field label="Their link goes to" hint="ReachAI gives them a short link to this page and counts every visit. Leave it empty for a code only.">
              <span className="relative">
                <Link2 size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                <input value={linkTo} onChange={(e) => setLinkTo(e.target.value)} placeholder="yoursite.com" aria-label="Their link goes to" className={`${control} pl-7`} />
              </span>
            </Field>
            {deal.tracking_code && <p className="text-[11px] text-zinc-500">Their code: <span className="font-mono text-zinc-900 dark:text-zinc-100">{deal.tracking_code}</span></p>}
          </section>
        </div>

        <div className="px-5 py-4 border-t border-zinc-200/70 dark:border-zinc-800/70 space-y-2">
          {error && <p className="text-[11px] text-rose-500">{error}</p>}
          <button type="button" onClick={save} disabled={busy || (!fee.trim() && !pct.trim())} className={`${btnPrimary} w-full h-9`}>
            {busy && <Loader2 size={13} className="animate-spin" />} {deal.posts?.length ? "Save and draft an update" : "Agree and draft the confirmation"}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
