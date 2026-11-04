/** What the campaigns page shows for each campaign. */
export type CampaignStatus = "draft" | "running" | "ready" | "empty" | "failed";

export interface Campaign {
  id: string;
  name: string;
  status: CampaignStatus;
  leadsCount: number;
  createdAt: string; // ISO
  updatedAt: string; // ISO; falls back to createdAt
}

/** Backend list row → card status. A finished run with no creators is "empty", not "active". */
export function campaignStatus(row: { status?: string | null; run_status?: string | null; leads_count?: number | null }): CampaignStatus {
  const s = (row.status || "").toLowerCase();
  const run = (row.run_status || "").toLowerCase();
  if (run === "failed") return "failed";
  if (s === "pending" || run === "running") return "running";
  if (s === "completed") return (row.leads_count ?? 0) > 0 ? "ready" : "empty";
  return "draft";
}

/** "just now", "5 min ago", "3 hours ago", "yesterday", "3 days ago", "Oct 12", "Oct 12, 2025" */
export function updatedLabel(iso: string, now: number = Date.now()): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, (now - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} hour${Math.floor(s / 3600) === 1 ? "" : "s"} ago`;
  const d = Math.floor(s / 86400);
  if (d === 1) return "yesterday";
  if (d < 7) return `${d} days ago`;
  const date = new Date(t);
  const sameYear = date.getFullYear() === new Date(now).getFullYear();
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", ...(sameYear ? {} : { year: "numeric" }) });
}
