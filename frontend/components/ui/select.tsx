"use client";

import { Select as S } from "radix-ui";
import { Check, ChevronDown } from "lucide-react";

export type SelectOption<T extends string> = { value: T; label: string; hint?: string };

/** The app's dropdown (docs/UI_GUIDE.md): 30px, text-xs, zinc; never the browser's own select. */
export function Select<T extends string>({ value, onChange, options, label, className = "" }: {
  value: T;
  onChange: (v: T) => void;
  options: SelectOption<T>[];
  label: string;
  className?: string;
}) {
  return (
    <S.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <S.Trigger
        aria-label={label}
        className={`h-[30px] w-full inline-flex items-center justify-between gap-2 px-2.5 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent text-zinc-900 dark:text-zinc-100 hover:bg-zinc-50 dark:hover:bg-zinc-900 focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600 data-[placeholder]:text-zinc-400 ${className}`}
      >
        <S.Value />
        <S.Icon><ChevronDown size={13} className="opacity-60" /></S.Icon>
      </S.Trigger>
      <S.Portal>
        <S.Content position="popper" sideOffset={4} className="z-50 min-w-[var(--radix-select-trigger-width)] max-h-72 overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0d0e] shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <S.Viewport className="p-1">
            {options.map((o) => (
              <S.Item
                key={o.value}
                value={o.value}
                className="relative flex flex-col gap-0.5 pl-7 pr-2 py-1.5 text-xs rounded-[4px] text-zinc-800 dark:text-zinc-200 outline-none cursor-pointer data-[highlighted]:bg-zinc-100 dark:data-[highlighted]:bg-zinc-800"
              >
                <S.ItemIndicator className="absolute left-2 top-2"><Check size={12} /></S.ItemIndicator>
                <S.ItemText>{o.label}</S.ItemText>
                {o.hint && <span className="text-[11px] text-zinc-500">{o.hint}</span>}
              </S.Item>
            ))}
          </S.Viewport>
        </S.Content>
      </S.Portal>
    </S.Root>
  );
}
