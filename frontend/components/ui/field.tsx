"use client";

import { useState } from "react";
import { control } from "@/lib/ui";

/** A labelled form field (docs/UI_GUIDE.md): sentence-case 11px label above the control. */
export function Field({ label, hint, children, className = "" }: { label: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`flex flex-col gap-1 min-w-0 ${className}`}>
      <span className="text-[11px] text-zinc-500">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-zinc-400">{hint}</span>}
    </label>
  );
}

/** Local text state that resets when the saved value changes (another save, or a different item opened). */
function useSynced(value: string | null) {
  const [v, setV] = useState(value ?? "");
  const [prev, setPrev] = useState(value);
  if (value !== prev) {
    setPrev(value);
    setV(value ?? "");
  }
  return [v, setV] as const;
}

/** Text input that saves when you leave it (or press Enter). */
export function Input({ value, onSave, placeholder, prefix, type = "text", inputMode }: {
  value: string | null;
  onSave: (v: string | null) => void;
  placeholder?: string;
  prefix?: string;
  type?: "text" | "date" | "url";
  inputMode?: "decimal" | "numeric" | "text" | "url";
}) {
  const [v, setV] = useSynced(value);
  const commit = () => {
    const next = v.trim() === "" ? null : v.trim();
    if (next !== (value ?? null)) onSave(next);
  };
  return (
    <div className="relative">
      {prefix && <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-zinc-400 pointer-events-none">{prefix}</span>}
      <input
        type={type}
        inputMode={inputMode}
        value={v}
        placeholder={placeholder}
        onChange={(e) => {
          setV(e.target.value);
          if (type === "date") onSave(e.target.value || null); // dates save as soon as they're picked
        }}
        onBlur={type === "date" ? undefined : commit}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        className={`${control} ${prefix ? "pl-6" : ""} [color-scheme:light] dark:[color-scheme:dark]`}
      />
    </div>
  );
}

/** Number input (money, %, days): keeps only digits and a dot; empty = null. */
export function NumberInput({ value, onSave, placeholder, prefix }: { value: number | null; onSave: (v: number | null) => void; placeholder?: string; prefix?: string }) {
  return (
    <Input
      value={value == null ? null : String(value)}
      inputMode="decimal"
      placeholder={placeholder}
      prefix={prefix}
      onSave={(s) => {
        if (s === null) return onSave(null);
        const n = Number(s.replace(/[^\d.]/g, ""));
        if (Number.isFinite(n)) onSave(n);
      }}
    />
  );
}

export function TextArea({ value, onSave, placeholder, rows = 3, maxLength = 4000 }: { value: string | null; onSave: (v: string | null) => void; placeholder?: string; rows?: number; maxLength?: number }) {
  const [v, setV] = useSynced(value);
  return (
    <textarea
      value={v}
      rows={rows}
      placeholder={placeholder}
      onChange={(e) => setV(e.target.value.slice(0, maxLength))}
      onBlur={() => (v || null) !== (value ?? null) && onSave(v || null)}
      className="w-full px-2.5 py-2 text-xs rounded-md border border-zinc-200 dark:border-zinc-800 bg-transparent text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none focus:border-zinc-400 dark:focus:border-zinc-600 resize-none leading-relaxed"
    />
  );
}
