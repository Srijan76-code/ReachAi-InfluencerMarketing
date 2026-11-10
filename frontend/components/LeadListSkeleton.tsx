/** Placeholder rows shaped like InfluencerRow, shown while a campaign's results load. */
export function LeadListSkeleton({ rows = 6 }: { rows?: number }) {
  const bar = "rounded bg-zinc-200/70 dark:bg-zinc-800/70";
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading creators">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-stretch gap-2" style={{ opacity: 1 - i * 0.12 }}>
          <div className="w-10 flex-shrink-0" />
          <div className="flex-1 min-w-0 rounded-lg border border-zinc-200/50 dark:border-zinc-800/50 bg-white dark:bg-[#0c0d0e] overflow-hidden">
            <div className="flex items-center gap-5 px-4 py-3 animate-pulse motion-reduce:animate-none">
              <div className={`${bar} w-5 h-3`} />
              <div className="flex items-center gap-3 min-w-[240px] flex-1">
                <div className={`${bar} w-8 h-8 rounded-[6px]`} />
                <div className="flex flex-col gap-1.5">
                  <div className={`${bar} h-3.5 w-36`} />
                  <div className={`${bar} h-3 w-20`} />
                </div>
              </div>
              <div className="hidden sm:flex items-center gap-10 px-8">
                <div className={`${bar} h-6 w-10`} />
                <div className={`${bar} h-6 w-10`} />
              </div>
              <div className="flex items-center gap-10 ml-auto">
                <div className={`${bar} hidden md:block h-6 w-20`} />
                <div className={`${bar} hidden md:block h-6 w-20`} />
                <div className={`${bar} h-6 w-14`} />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
