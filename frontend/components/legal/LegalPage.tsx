import Link from "next/link";

/** Plain page for the privacy policy and terms: same look as the rest of ReachAI. */
export function LegalPage({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-zinc-50 dark:bg-[#08090a] px-4 pt-24 pb-16">
      <article className="mx-auto max-w-2xl space-y-6 text-[13px] leading-relaxed text-zinc-700 dark:text-zinc-300 [&_h2]:text-[14px] [&_h2]:font-medium [&_h2]:text-zinc-900 [&_h2]:dark:text-zinc-100 [&_h2]:pt-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_a]:underline [&_a]:underline-offset-4">
        <header className="space-y-1">
          <h1 className="text-[18px] font-medium text-zinc-900 dark:text-zinc-100">{title}</h1>
          <p className="text-[11px] text-zinc-500">Last updated {updated}</p>
        </header>
        {children}
        <footer className="pt-6 text-[11px] text-zinc-500 flex gap-4">
          <Link href="/">ReachAI</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </footer>
      </article>
    </main>
  );
}

export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL;

export function Contact() {
  return SUPPORT_EMAIL ? <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> : <>the support address on our Google sign-in screen</>;
}
