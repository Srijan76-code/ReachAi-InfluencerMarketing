"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";

const REF_KEY = "reachai_ref";

/** Invite link: remember the code, then sign up. The code is claimed once the account exists (Header). */
export default function JoinPage() {
  const { code } = useParams<{ code: string }>();
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoaded) return;
    try {
      if (code && /^[a-z0-9]{4,32}$/i.test(code)) localStorage.setItem(REF_KEY, code.toLowerCase());
    } catch {
      // storage blocked: the invite simply doesn't count
    }
    router.replace(isSignedIn ? "/campaign" : `/sign-up?redirect_url=${encodeURIComponent("/campaign")}`);
  }, [code, isLoaded, isSignedIn, router]);

  return (
    <main className="min-h-screen grid place-items-center text-xs text-zinc-500">
      You&apos;ve been invited to ReachAI. Taking you to sign up…
    </main>
  );
}
