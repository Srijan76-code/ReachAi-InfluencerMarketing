"use client";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Field, Input, NumberInput } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { type Deal, DEAL_TYPES, DELIVERABLES, USAGE, money } from "@/data/deals";

const opts = <T extends string>(list: readonly (readonly [T, string])[]) => list.map(([value, l]) => ({ value, label: l }));
const ask = (fee: number | null | undefined, pct: number | null | undefined) =>
  fee == null && pct ? `${pct}% commission` : `${money(fee ?? 0)}${pct ? ` + ${pct}%` : ""}`;

/** The deal's terms and contact, in a side panel so the chat stays clean. Changes save as you go. */
export function DealDetails({ open, onOpenChange, deal, save }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  deal: Deal;
  save: (patch: Record<string, unknown>) => void;
}) {
  const a = deal.advice;
  const commission = deal.deal_type === "base_plus_commission" || deal.deal_type === "affiliate";
  const talking = deal.stage === "contacted" || deal.stage === "negotiating";
  const facts = [
    ["Fair price", a.fair_high != null ? `${money(a.fair_low)}–${money(a.fair_high)}` : "Not set"],
    talking && deal.quoted_rate != null ? ["They ask", ask(deal.quoted_rate, deal.quoted_commission_pct)] : null,
    !talking && deal.agreed_rate != null ? ["Agreed", ask(deal.agreed_rate, deal.deal_type !== "flat" ? deal.commission_pct : null)] : null,
  ].filter(Boolean) as [string, string][];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-sm bg-white dark:bg-[#0c0d0e] border-zinc-200 dark:border-zinc-800 p-0 gap-0">
        <SheetHeader className="px-5 pt-5 pb-4 border-b border-zinc-200/70 dark:border-zinc-800/70">
          <SheetTitle className="text-[14px] font-medium">{deal.name}</SheetTitle>
          <SheetDescription className="text-xs">Terms and contact. Changes save as you go.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          <dl className="grid grid-cols-2 gap-3">
            {facts.map(([k, v]) => (
              <div key={k} className="rounded-lg bg-zinc-50 dark:bg-[#121314] px-3 py-2">
                <dt className="text-[11px] text-zinc-500">{k}</dt>
                <dd className="text-[13px] font-mono text-zinc-900 dark:text-zinc-100 mt-0.5">{v}</dd>
              </div>
            ))}
          </dl>

          <section className="space-y-3">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Contact</h3>
            <Field label="Their email" hint="With Gmail connected, messages go from your address to this one.">
              <Input value={deal.contact_email ?? null} onSave={(v) => save({ contact_email: v })} placeholder="their@email.com" />
            </Field>
          </section>

          <section className="space-y-3">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Terms</h3>
            <Field label="Deliverable"><Select label="Deliverable" value={deal.deliverable} onChange={(v) => save({ deliverable: v })} options={opts(DELIVERABLES)} /></Field>
            <Field label="Deal type"><Select label="Deal type" value={deal.deal_type} onChange={(v) => save({ deal_type: v })} options={opts(DEAL_TYPES)} /></Field>
            {commission && <Field label="Commission (%)"><NumberInput value={deal.commission_pct} onSave={(v) => save({ commission_pct: v })} placeholder="10" /></Field>}
            <Field label="Usage rights"><Select label="Usage rights" value={deal.usage_rights} onChange={(v) => save({ usage_rights: v })} options={opts(USAGE)} /></Field>
            {!talking && <Field label="Post by"><Input type="date" value={deal.post_by} onSave={(v) => save({ post_by: v })} /></Field>}
          </section>

          <section className="space-y-3">
            <h3 className="text-[12px] font-medium text-zinc-900 dark:text-zinc-100">Fair price</h3>
            <p className="text-[11px] text-zinc-500 -mt-1">ReachAI never offers more than a little above this, or more than your budget left.</p>
            <div className="grid grid-cols-2 gap-3">
              <Field label="From"><NumberInput prefix="$" value={a.fair_low} onSave={(v) => save({ fair_low: v })} placeholder="Low" /></Field>
              <Field label="To"><NumberInput prefix="$" value={a.fair_high} onSave={(v) => save({ fair_high: v })} placeholder="High" /></Field>
            </div>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}
