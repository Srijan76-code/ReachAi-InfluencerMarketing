/** Shown for a moment while a campaign tab loads (same placeholders as the rest of the app). */
export default function Loading() {
  const bar = "rounded bg-zinc-200/70 dark:bg-zinc-800/70 animate-pulse motion-reduce:animate-none";
  return (
    <div className="space-y-4 pt-2" aria-busy="true" aria-label="Loading">
      <div className={`${bar} h-5 w-40`} />
      <div className={`${bar} h-24 w-full`} />
      <div className={`${bar} h-14 w-full`} />
      <div className={`${bar} h-14 w-full`} />
    </div>
  );
}
