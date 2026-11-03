import type { ReactNode } from "react";
import { DocsLayout } from "fumadocs-ui/layouts/docs";
import { RootProvider } from "fumadocs-ui/provider/next";
import { source } from "@/lib/source";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    // The app already has a theme provider (next-themes), so Fumadocs reuses it.
    <RootProvider theme={{ enabled: false }} search={{ options: { api: "/docs-search" } }}>
      <DocsLayout
        tree={source.getPageTree()}
        nav={{
          title: (
            <span className="flex items-center gap-2 font-semibold text-sm tracking-tight">
              <span className="w-6 h-6 bg-zinc-900 dark:bg-neutral-300 rounded-md flex items-center justify-center">
                <span className="w-2.5 h-2.5 bg-white dark:bg-zinc-900 rounded-sm" />
              </span>
              ReachAI Docs
            </span>
          ),
          url: "/docs",
        }}
        links={[{ text: "Back to app", url: "/campaign" }]}
      >
        {children}
      </DocsLayout>
    </RootProvider>
  );
}
