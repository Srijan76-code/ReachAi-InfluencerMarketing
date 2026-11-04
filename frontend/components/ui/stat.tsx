import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Tiles of numbers (docs/UI_GUIDE.md), the same as the creator panel's Performance metrics. */
export function StatStrip({ children, cols = 4 }: { children: React.ReactNode; cols?: 2 | 3 | 4 }) {
  // 4 tiles wrap to 2×2 on phones: draw the inner lines for that layout only.
  const grid =
    cols === 4
      ? "grid-cols-2 md:grid-cols-4 max-md:[&>*:nth-child(2)]:border-r-0 max-md:[&>*:nth-child(-n+2)]:border-b"
      : cols === 3
        ? "grid-cols-3"
        : "grid-cols-2";
  return <div className={`grid ${grid} rounded border border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-100 dark:bg-[#121314] overflow-hidden`}>{children}</div>;
}

export function StatTile({ icon, label, value, sub, tone, help }: {
  icon?: React.ReactNode;
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "good" | "warn" | "bad";
  help?: string;
}) {
  const color = tone === "good" ? "text-emerald-600 dark:text-emerald-400" : tone === "warn" ? "text-amber-600 dark:text-amber-400" : tone === "bad" ? "text-rose-500" : "text-zinc-900 dark:text-zinc-200";
  const body = (
    <div className={`p-3.5 flex flex-col gap-1.5 min-w-0 border-r last:border-r-0 border-zinc-200/60 dark:border-zinc-800/60 ${help ? "cursor-help hover:bg-zinc-200/40 dark:hover:bg-zinc-800/20 transition-colors" : ""}`}>
      <div className="flex items-center gap-1.5 min-w-0">
        {icon && <span className="text-zinc-400 dark:text-zinc-600 shrink-0">{icon}</span>}
        <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400 truncate">{label}</span>
      </div>
      <span className={`text-[13px] font-semibold truncate ${icon ? "pl-[1.125rem]" : ""} ${color}`}>{value}</span>
      {sub && <span className={`text-[11px] text-zinc-500 truncate ${icon ? "pl-[1.125rem]" : ""}`}>{sub}</span>}
    </div>
  );
  if (!help) return body;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{body}</TooltipTrigger>
      <TooltipContent side="top" className="bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-xs shadow-xl max-w-[220px] text-zinc-700 dark:text-zinc-300">{help}</TooltipContent>
    </Tooltip>
  );
}

/** A section header inside a side panel, the same as the creator panel's. */
export function SectionHeader({ icon, children, right }: { icon?: React.ReactNode; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <h3 className="text-[11px] font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider flex items-center gap-2">
        {icon}
        {children}
      </h3>
      {right}
    </div>
  );
}
