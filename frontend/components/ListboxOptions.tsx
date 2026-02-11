"use client";

import { ListBox, ListBoxItem } from "react-aria-components";

import { Label } from "@/components/ui/label";

export default function ListboxOptions() {
  return (
    <div className="*:not-first:mt-2">
      <Label>Listbox with multiple options</Label>
      <div className="overflow-hidden rounded-md border border-input">
        <ListBox
          aria-label="Select framework"
          className="max-h-72 min-h-20 space-y-1 overflow-auto bg-background p-1 text-sm shadow-xs transition-[color,box-shadow]"
          defaultSelectedKeys={["react", "vue"]}
          selectionMode="multiple"
        >
          <ListBoxItem
            className="relative rounded px-2 py-1.5 outline-none data-disabled:cursor-not-allowed data-focus-visible:border-ring data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground data-disabled:opacity-50 data-focus-visible:ring-[3px] data-focus-visible:ring-ring/50"
            id="react"
          >
            React
          </ListBoxItem>
          <ListBoxItem
            className="relative rounded px-2 py-1.5 outline-none data-disabled:cursor-not-allowed data-focus-visible:border-ring data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground data-disabled:opacity-50 data-focus-visible:ring-[3px] data-focus-visible:ring-ring/50"
            id="vue"
          >
            Vue
          </ListBoxItem>
          <ListBoxItem
            className="relative rounded px-2 py-1.5 outline-none data-disabled:cursor-not-allowed data-focus-visible:border-ring data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground data-disabled:opacity-50 data-focus-visible:ring-[3px] data-focus-visible:ring-ring/50"
            id="angular"
          >
            Angular
          </ListBoxItem>
          <ListBoxItem
            className="relative rounded px-2 py-1.5 outline-none data-disabled:cursor-not-allowed data-focus-visible:border-ring data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground data-disabled:opacity-50 data-focus-visible:ring-[3px] data-focus-visible:ring-ring/50"
            id="svelte"
          >
            Svelte
          </ListBoxItem>
        </ListBox>
      </div>
      <p
        aria-live="polite"
        className="mt-2 text-muted-foreground text-xs"
        role="region"
      >
        Built with{" "}
        <a
          className="underline hover:text-foreground"
          href="https://react-spectrum.adobe.com/react-aria/ListBox.html"
          rel="noreferrer noopener nofollow"
          target="_blank"
        >
          React Aria
        </a>
      </p>
    </div>
  );
}
