"use client";

import { useEffect, useId, useRef, useState } from "react";

/* Mermaid diagrams for the docs, drawn in the app's own look (Geist, zinc neutrals, 10px radius).
   mermaid is loaded only when a diagram is on screen, and redrawn when light/dark changes. */

const THEMES = {
  light: {
    background: "transparent", primaryColor: "#ffffff", primaryTextColor: "#18181b", primaryBorderColor: "#e4e4e7",
    lineColor: "#a1a1aa", secondaryColor: "#fafafa", tertiaryColor: "#f4f4f5", clusterBkg: "#fafafa",
    clusterBorder: "#e4e4e7", edgeLabelBackground: "#fafafa", actorBkg: "#ffffff", actorBorder: "#e4e4e7",
    actorTextColor: "#18181b", signalColor: "#71717a", signalTextColor: "#3f3f46", noteBkgColor: "#f4f4f5",
    noteBorderColor: "#e4e4e7",
  },
  dark: {
    background: "transparent", primaryColor: "#0c0d0e", primaryTextColor: "#e4e4e7", primaryBorderColor: "#27272a",
    lineColor: "#52525b", secondaryColor: "#121314", tertiaryColor: "#18181b", clusterBkg: "#0c0d0e",
    clusterBorder: "#27272a", edgeLabelBackground: "#08090a", actorBkg: "#0c0d0e", actorBorder: "#27272a",
    actorTextColor: "#e4e4e7", signalColor: "#71717a", signalTextColor: "#a1a1aa", noteBkgColor: "#18181b",
    noteBorderColor: "#27272a",
  },
};

function currentMode(): "light" | "dark" {
  return typeof document !== "undefined" && document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function Mermaid({ chart, caption }: { chart: string; caption?: string }) {
  const id = useId().replace(/:/g, "");
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const [mode, setMode] = useState<"light" | "dark">("light");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMode(currentMode());
    const obs = new MutationObserver(() => setMode(currentMode()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
          themeVariables: {
            ...THEMES[mode],
            fontSize: "14px",
            // charts: the app's blue accent, axes in zinc
            xyChart: { plotColorPalette: "#3b82f6", backgroundColor: "transparent",
                       titleColor: THEMES[mode].primaryTextColor, xAxisLabelColor: THEMES[mode].signalTextColor,
                       yAxisLabelColor: THEMES[mode].signalTextColor, xAxisLineColor: THEMES[mode].lineColor,
                       yAxisLineColor: THEMES[mode].lineColor, xAxisTickColor: THEMES[mode].lineColor,
                       yAxisTickColor: THEMES[mode].lineColor, xAxisTitleColor: THEMES[mode].signalTextColor,
                       yAxisTitleColor: THEMES[mode].signalTextColor },
          },
          flowchart: { curve: "basis", padding: 12, nodeSpacing: 28, rankSpacing: 36, useMaxWidth: false },
          xyChart: { useMaxWidth: true },
          sequence: { actorMargin: 60, messageMargin: 28, useMaxWidth: false },
        });
        const { svg } = await mermaid.render(`m${id}${mode}`, chart.trim());
        if (!cancelled) {
          setSvg(svg);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String((e as Error)?.message ?? e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart, id, mode]);

  return (
    <figure className="not-prose rd-fade my-6">
      <div
        ref={ref}
        className="overflow-x-auto rounded-[10px] border border-zinc-200 bg-white p-4 dark:border-white/10 dark:bg-[#0c0d0e] [&_svg]:mx-auto [&_svg]:h-auto"
        // svg is produced by mermaid from a chart written in our own MDX, with securityLevel "strict"
        dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
      >
        {!svg && !error ? <div className="h-24 animate-pulse rounded-md bg-zinc-100 dark:bg-zinc-900" /> : null}
      </div>
      {error && <pre className="mt-2 text-xs text-rose-500">Diagram error: {error}</pre>}
      {caption && <figcaption className="mt-2 text-center text-[12px] text-zinc-500">{caption}</figcaption>}
    </figure>
  );
}
