"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, Copy, Instagram, Mail, Twitter } from "lucide-react";
import { SignUpButton, Show } from "@clerk/nextjs";
import { Sheet, SheetTrigger } from "@/components/ui/sheet";
import { InfluencerRow } from "@/app/ListOfInfluencer/InfluencerRow";
import { InfluencerDetailSheet } from "@/app/ListOfInfluencer/InfluencerDetailSheet";
import { demoBrief, demoCollaboration, demoLeads, demoPitches, type DemoChannel } from "@/data/demo/campaign";

type Tab = "leads" | "outreach";

const card = "bg-white dark:bg-[#0c0d0e] border border-zinc-200 dark:border-zinc-800/80 rounded-xl";
const label = "text-[11px] font-medium uppercase tracking-[0.12em] text-zinc-400 dark:text-zinc-500";

function BriefCard({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className={`${card} p-5 flex flex-col gap-3 min-w-0`}>
      <span className={label}>{title}</span>
      <dl className="flex flex-col gap-2">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-col gap-0.5">
            <dt className="text-[12px] text-zinc-500 dark:text-zinc-400">{k}</dt>
            <dd className="text-[13px] text-zinc-900 dark:text-zinc-100">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          setCopied(false);
        }
      }}
      className="flex items-center gap-1.5 text-[12px] text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function OutreachTab() {
  const leadsById = useMemo(() => new Map(demoLeads.map((l) => [l.id, l])), []);
  const [activeId, setActiveId] = useState(demoPitches[0]?.creatorId);
  const pitch = demoPitches.find((p) => p.creatorId === activeId) ?? demoPitches[0];
  const channels = (["email", "instagram", "twitter"] as DemoChannel[]).filter((c) => pitch?.[c]);
  const [channel, setChannel] = useState<DemoChannel>(channels[0] ?? "instagram");
  const activeChannel = channels.includes(channel) ? channel : channels[0];
  const lead = pitch ? leadsById.get(pitch.creatorId) : undefined;

  if (!pitch) return null;
  const body = activeChannel === "email" ? pitch.email?.body ?? "" : (pitch[activeChannel] as string) ?? "";
  const icons = { email: Mail, instagram: Instagram, twitter: Twitter };

  return (
    <div className="grid grid-cols-1 md:grid-cols-[260px_minmax(0,1fr)] gap-4">
      <div className={`${card} p-2 flex flex-col gap-1 h-fit`}>
        {demoPitches.map((p) => {
          const l = leadsById.get(p.creatorId);
          const active = p.creatorId === pitch.creatorId;
          return (
            <button
              key={p.creatorId}
              type="button"
              onClick={() => setActiveId(p.creatorId)}
              className={`flex items-center justify-between gap-2 text-left px-3 py-2 rounded-lg text-[13px] transition-colors ${
                active
                  ? "bg-zinc-100 dark:bg-zinc-800/60 text-zinc-900 dark:text-zinc-100"
                  : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-900"
              }`}
            >
              <span className="truncate">{l?.title ?? p.creatorId}</span>
              <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                Ready
              </span>
            </button>
          );
        })}
      </div>

      <div className={`${card} p-5 flex flex-col gap-5 min-w-0`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1 min-w-0">
            <span className="text-[15px] font-medium text-zinc-900 dark:text-zinc-100">{lead?.title}</span>
            <span className="text-[12px] text-zinc-500 dark:text-zinc-400">{demoCollaboration}</span>
          </div>
          <div className="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-900 p-1 rounded-lg">
            {channels.map((c) => {
              const Icon = icons[c];
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => setChannel(c)}
                  className={`flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-md capitalize transition-colors ${
                    activeChannel === c
                      ? "bg-white dark:bg-[#0c0d0e] text-zinc-900 dark:text-zinc-100 shadow-sm"
                      : "text-zinc-500 dark:text-zinc-400"
                  }`}
                >
                  <Icon size={12} />
                  {c === "twitter" ? "X" : c}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className={label}>Pitch angle</span>
          <p className="text-[13px] text-zinc-600 dark:text-zinc-300">{pitch.pitchAngle}</p>
        </div>

        <div className="flex flex-col gap-2 border-t border-zinc-100 dark:border-zinc-800/80 pt-5">
          <div className="flex items-center justify-between">
            <span className={label}>{activeChannel === "email" ? "Email" : "Message"}</span>
            <CopyButton text={activeChannel === "email" ? `${pitch.email?.subject}\n\n${body}` : body} />
          </div>
          {activeChannel === "email" && (
            <p className="text-[13px] font-medium text-zinc-900 dark:text-zinc-100">Subject: {pitch.email?.subject}</p>
          )}
          <p className="text-[13px] leading-relaxed text-zinc-700 dark:text-zinc-300 whitespace-pre-line">{body}</p>
        </div>
      </div>
    </div>
  );
}

export default function DemoCampaign() {
  const [tab, setTab] = useState<Tab>("leads");
  const strongBuys = demoLeads.filter((l) => l.deal_status === "Strong Buy").length;
  const { brand, audience, campaign } = demoBrief;

  return (
    <main className="pt-16 pb-24 px-6">
      <div className="max-w-6xl mx-auto flex flex-col gap-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-2">
            <span className="inline-flex w-fit items-center gap-2 text-[11px] font-medium text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 rounded-full">
              Demo campaign · sample data, read-only
            </span>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
              {brand.name}: data science bootcamp
            </h1>
            <p className="text-[13px] text-zinc-500 dark:text-zinc-400 max-w-2xl">
              A finished campaign: the brief a founder wrote, the creators ReachAI found and ranked on YouTube, and the
              first messages it prepared.
            </p>
          </div>
          <Show when="signed-out">
            <SignUpButton>
              <button className="group text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-4 py-2 rounded-full flex items-center gap-1.5 hover:opacity-90 transition-all shadow-sm">
                Run your own campaign
                <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
            </SignUpButton>
          </Show>
          <Show when="signed-in">
            <Link
              href="/campaign"
              className="group text-[13px] font-medium bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-4 py-2 rounded-full flex items-center gap-1.5 hover:opacity-90 transition-all shadow-sm"
            >
              Run your own campaign
              <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </Show>
        </div>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <BriefCard
            title="Brand"
            rows={[
              ["Product", brand.outcome],
              ["Industry", `${brand.industry} · ${brand.businessModel}`],
              ["Price", brand.priceRange],
            ]}
          />
          <BriefCard
            title="Audience"
            rows={[
              ["Who buys", audience.persona],
              ["Where", audience.locations.join(", ")],
              ["Languages", audience.languages.join(", ")],
            ]}
          />
          <BriefCard
            title="Campaign"
            rows={[
              ["Goal", campaign.goal],
              ["Creator type", campaign.creatorType],
              ["Budget · creators", `$${campaign.budget.toLocaleString()} · ${campaign.creatorCount} creators`],
            ]}
          />
        </section>

        <div className="flex items-center gap-1 border-b border-zinc-200 dark:border-zinc-800">
          {([
            ["leads", `Creators (${demoLeads.length})`],
            ["outreach", `Outreach (${demoPitches.length})`],
          ] as [Tab, string][]).map(([key, text]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`text-[13px] px-3 py-2 -mb-px border-b-2 transition-colors ${
                tab === key
                  ? "border-zinc-900 dark:border-zinc-100 text-zinc-900 dark:text-zinc-100 font-medium"
                  : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200"
              }`}
            >
              {text}
            </button>
          ))}
        </div>

        {tab === "leads" ? (
          <section className="flex flex-col gap-3">
            <p className="text-[13px] text-zinc-500 dark:text-zinc-400">
              {strongBuys} strong buys. Select a creator to see their numbers, fair price and why they fit.
            </p>
            <div className={`${card} overflow-hidden`}>
              <div className="overflow-x-auto">
                <div className="min-w-[760px] divide-y divide-zinc-100 dark:divide-zinc-800/60">
                  {demoLeads.map((lead, index) => (
                    <Sheet key={lead.id}>
                      <SheetTrigger asChild>
                        <div>
                          <InfluencerRow influencer={lead} rank={index + 1} />
                        </div>
                      </SheetTrigger>
                      <InfluencerDetailSheet influencer={lead} />
                    </Sheet>
                  ))}
                </div>
              </div>
            </div>
          </section>
        ) : (
          <OutreachTab />
        )}
      </div>
    </main>
  );
}
