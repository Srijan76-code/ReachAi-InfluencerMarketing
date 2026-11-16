"use client";

import { useState } from "react";
import { ChevronDown, Globe, Loader2 } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useCampaignStore } from "@/store/campaignStore";
import { useApi } from "@/lib/api";
import { btn, btnPrimary, control } from "@/lib/ui";
import { SITE_FIELD_LABELS } from "@/lib/siteBrief";

const MODELS: Record<string, string> = { "1": "B2B", "2": "B2C", "3": "D2C" };
const PRICES: Record<string, string> = { "1": "Low (<$50)", "2": "Mid ($50–$500)", "3": "High ($500+)" };

/** "Start from your website" (F1.24). The site fills the brief, Jev checks every field, and only the fields it
 * wasn't sure about are asked. What it filled is folded away until the founder wants to look. */
export default function SiteBriefBox() {
  const api = useApi();
  const applySiteBrief = useCampaignStore((s) => s.applySiteBrief);
  const setField = useCampaignStore((s) => s.setField);
  const site = useCampaignStore((s) => s.site);
  const showAll = useCampaignStore((s) => s.showAllFields);
  const values = useCampaignStore(useShallow((s) => ({
    brand_name: s.brandName,
    core_outcome: s.pitch,
    target_persona: s.targetAudience,
    industry: s.industry,
    business_model: MODELS[s.businessModel] || "",
    price_range: PRICES[s.productPriceRange] || "",
    competitors: s.competitors.join(", "),
  })));
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function read() {
    if (!url.trim() || busy) return;
    setBusy(true);
    setError(null);
    setOpen(false);
    try {
      const res = await api("/api/campaigns/brief-from-url", { method: "POST", data: { url: url.trim() } });
      const d = res.data;
      applySiteBrief(d.details);
      setField("showAllFields", false);
      setField("site", { url: d.url, confirmed: d.confirmed || [], unchecked: d.unchecked || [], missing: d.missing || [], checked: !!d.checked });
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "We couldn't read that site. Fill the brief in by hand.");
    } finally {
      setBusy(false);
    }
  }

  const names = (keys: string[]) => keys.map((k) => (SITE_FIELD_LABELS[k] || k).toLowerCase()).join(", ");
  const host = site ? site.url.replace(/^https?:\/\//, "").replace(/\/$/, "") : "";

  return (
    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg p-4 bg-white dark:bg-[#0c0d0e] space-y-3">
      <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-900 dark:text-zinc-100">
        <Globe size={13} className="text-zinc-500" /> Start from your website
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          read();
        }}
      >
        <input
          className={control}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="yourproduct.com"
          inputMode="url"
          aria-label="Your website address"
        />
        <button type="submit" className={btnPrimary} disabled={busy || !url.trim()}>
          {busy && <Loader2 size={12} className="animate-spin" />}
          {busy ? "Reading…" : site ? "Read again" : "Fill the brief"}
        </button>
      </form>
      {error && <p className="text-[11px] text-rose-500">{error}</p>}
      {!site && !error && (
        <p className="text-[11px] text-zinc-400">We read your public page and fill what it clearly says. You only answer what we aren't sure about.</p>
      )}

      {site && (
        <div className="space-y-2 pt-1">
          {site.checked ? (
            <p className="text-[13px] text-zinc-900 dark:text-zinc-100">
              Filled {site.confirmed.length} of 7 from {host}
              {site.missing.length > 0 && <span className="text-zinc-500"> · {site.missing.length} need you</span>}
            </p>
          ) : (
            <p className="text-[13px] text-amber-600 dark:text-amber-500">
              We filled what we could from {host} but couldn't double-check it. Please look at every field below.
            </p>
          )}

          {site.checked && site.missing.length > 0 && (
            <p className="text-[11px] text-zinc-500">
              We weren't 100% sure about {names(site.missing)}. Please fill {site.missing.length === 1 ? "it" : "them"} in below.
            </p>
          )}

          {site.confirmed.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                className="inline-flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
              >
                <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
                {open ? "Hide what we filled" : "Show what we filled"}
              </button>
              {open && (
                <div className="mt-2 rounded-md bg-zinc-100 dark:bg-[#121314] p-3 space-y-2">
                  {site.confirmed.map((k) => (
                    <div key={k} className="grid grid-cols-[110px_1fr] gap-2 text-xs">
                      <span className="text-[11px] text-zinc-500 pt-px">{SITE_FIELD_LABELS[k] || k}</span>
                      <span className="text-zinc-900 dark:text-zinc-100 break-words">{values[k as keyof typeof values] || "—"}</span>
                    </div>
                  ))}
                  <button type="button" className={btn} onClick={() => setField("showAllFields", !showAll)}>
                    {showAll ? "Hide these fields again" : "Edit these fields"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
