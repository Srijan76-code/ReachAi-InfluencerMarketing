import type { CSSProperties, ReactNode } from "react";

/* Small, themed building blocks for the docs (MDX). They use the app's own tokens (zinc neutrals,
   Geist, 10px radius) and status colours only where they carry meaning. Motion is CSS-only and
   switched off for people who prefer reduced motion (see globals.css, "docs motion"). */

type Stat = { value: string; label: string; note?: string };

/** A row of headline numbers. Every number should be measured; put how in `note`. */
export function Stats({ items }: { items: Stat[] }) {
  return (
    <div className="not-prose my-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {items.map((s, i) => (
        <div
          key={s.label}
          className="rd-rise rounded-[10px] border border-zinc-200 bg-white p-4 dark:border-white/10 dark:bg-[#0c0d0e]"
          style={{ "--rd-i": i } as CSSProperties}
        >
          <div className="font-mono text-xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{s.value}</div>
          <div className="mt-1 text-[13px] font-medium text-zinc-700 dark:text-zinc-300">{s.label}</div>
          {s.note && <div className="mt-1 text-[11px] leading-snug text-zinc-500">{s.note}</div>}
        </div>
      ))}
    </div>
  );
}

type FlowStep = { title: string; detail?: string; tag?: string };

/** A step-by-step flow (left to right on wide screens, top to bottom on phones). */
export function Flow({ steps }: { steps: FlowStep[] }) {
  if (steps.length > 5) {
    // long flows: a numbered grid reads better than one cramped row
    return (
      <ol className="not-prose my-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {steps.map((s, i) => (
          <li
            key={s.title}
            className="rd-rise rounded-[10px] border border-zinc-200 bg-white px-3.5 py-3 dark:border-white/10 dark:bg-[#0c0d0e]"
            style={{ "--rd-i": i } as CSSProperties}
          >
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[10px] font-semibold text-zinc-400">{String(i + 1).padStart(2, "0")}</span>
              <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">{s.title}</span>
              {s.tag && <span className="ml-auto font-mono text-[10px] text-zinc-400">{s.tag}</span>}
            </div>
            {s.detail && <p className="mt-1 text-[12px] leading-snug text-zinc-500">{s.detail}</p>}
          </li>
        ))}
      </ol>
    );
  }
  return (
    <ol className="not-prose my-6 flex flex-col gap-2 lg:flex-row lg:items-stretch lg:gap-0">
      {steps.map((s, i) => (
        <li key={s.title} className="flex flex-col lg:flex-1 lg:flex-row lg:items-stretch">
          <div
            className="rd-rise relative flex-1 lg:h-full rounded-[10px] border border-zinc-200 bg-white px-3.5 py-3 dark:border-white/10 dark:bg-[#0c0d0e]"
            style={{ "--rd-i": i } as CSSProperties}
          >
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-[10px] font-semibold text-zinc-400">{String(i + 1).padStart(2, "0")}</span>
              <span className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">{s.title}</span>
            </div>
            {s.detail && <p className="mt-1 text-[12px] leading-snug text-zinc-500">{s.detail}</p>}
            {s.tag && (
              <span className="mt-2 inline-block rounded-[4px] border border-zinc-200 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500 dark:border-white/10">
                {s.tag}
              </span>
            )}
          </div>
          {i < steps.length - 1 && (
            <span aria-hidden className="rd-fade self-center px-1.5 py-0.5 text-zinc-300 dark:text-zinc-600" style={{ "--rd-i": i + 0.5 } as CSSProperties}>
              <span className="lg:hidden">↓</span>
              <span className="hidden lg:inline">→</span>
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

const STATUS = {
  live: { text: "Live", cls: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
  soon: { text: "Coming soon", cls: "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20" },
} as const;

/** "Live" or "Coming soon". Docs only describe shipped features as live (see CLAUDE.md). */
export function Status({ is }: { is: keyof typeof STATUS }) {
  const s = STATUS[is];
  return (
    <span className={`not-prose ml-1 inline-flex translate-y-[-1px] items-center rounded-[4px] border px-1.5 py-0.5 align-middle text-[10px] font-semibold tracking-wide ${s.cls}`}>
      {s.text}
    </span>
  );
}

/** A plain, compact feature grid: title + one line each. */
export function Features({ items }: { items: { title: string; text: string; status?: keyof typeof STATUS }[] }) {
  return (
    <div className="not-prose my-6 grid gap-3 sm:grid-cols-2">
      {items.map((f, i) => (
        <div
          key={f.title}
          className="rd-rise rounded-[10px] border border-zinc-200 bg-white p-4 dark:border-white/10 dark:bg-[#0c0d0e]"
          style={{ "--rd-i": i } as CSSProperties}
        >
          <div className="text-[14px] font-semibold text-zinc-900 dark:text-zinc-100">
            {f.title}
            {f.status && <Status is={f.status} />}
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-zinc-500">{f.text}</p>
        </div>
      ))}
    </div>
  );
}

export function Lead({ children }: { children: ReactNode }) {
  // a div, not a <p>: MDX wraps the text in its own paragraph
  return <div className="rd-fade text-[17px] leading-relaxed text-zinc-600 dark:text-zinc-300 [&_p]:m-0">{children}</div>;
}
