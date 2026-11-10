import type { ScoreParts as Parts } from "@/data/influencerList";

/** "Why this score": the points each part adds or takes away, adding up to the final score.
 *  Numbers come from the backend (app/judge/combine.py), never recomputed here. */
const ROWS: { key: "fit" | "health" | "bonus" | "risk"; label: string; help: string; bar: string }[] = [
  { key: "fit", label: "Brand fit", help: "How well their content and audience match your brief", bar: "bg-blue-500" },
  { key: "health", label: "Channel health", help: "Steady views, real engagement, posting regularly", bar: "bg-emerald-500" },
  { key: "bonus", label: "Bonus", help: "Rising or on trend right now", bar: "bg-amber-500" },
  { key: "risk", label: "Risk", help: "Brand-safety and audience-quality concerns", bar: "bg-rose-500" },
];

export function ScoreParts({ parts, finalScore }: { parts: Parts; finalScore: number }) {
  const sum = parts.fit + parts.health + parts.bonus + parts.risk;
  const factor = parts.country_unknown_factor;
  const max = Math.max(1, ...ROWS.map((r) => Math.abs(parts[r.key] ?? 0)));
  return (
    <div className="rounded border border-zinc-200/60 dark:border-zinc-800/60 bg-zinc-100 dark:bg-[#121314] p-3.5 space-y-2.5">
      {ROWS.filter((r) => r.key !== "bonus" || parts.bonus).map((r) => {
        const v = parts[r.key] ?? 0;
        return (
          <div key={r.key} className="grid grid-cols-[110px_1fr_52px] items-center gap-3" title={r.help}>
            <span className="text-[12px] text-zinc-700 dark:text-zinc-300">{r.label}</span>
            <div className="h-1.5 rounded-full bg-zinc-200/70 dark:bg-zinc-800/80 overflow-hidden">
              <div className={`h-full rounded-full ${r.bar} transition-[width] duration-500`} style={{ width: `${(Math.abs(v) / max) * 100}%` }} />
            </div>
            <span className={`text-right font-mono text-[12px] ${v < 0 ? "text-rose-500" : "text-zinc-700 dark:text-zinc-300"}`}>
              {v < 0 ? "−" : "+"}{Math.abs(v).toFixed(1)}
            </span>
          </div>
        );
      })}
      <div className="border-t border-zinc-200/60 dark:border-zinc-800/60 pt-2.5 flex items-center justify-between text-[12px]">
        <span className="text-zinc-500">
          {factor ? (
            <>
              {sum.toFixed(1)} × {factor} <span title="The channel lists no country, so we can't confirm its audience is in your market">(country unknown)</span>
            </>
          ) : (
            "Score"
          )}
        </span>
        <span className="font-mono font-semibold text-zinc-900 dark:text-zinc-100">= {Math.round(finalScore)}</span>
      </div>
    </div>
  );
}
