"use client";

import { Suspense, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter, useSearchParams } from "next/navigation";
import { PricingView } from "@/components/pricing/PricingView";
import { useCredits } from "@/lib/credits";
import { useCheckout } from "@/lib/useCheckout";

function Pricing() {
  const { isSignedIn } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const credits = useCredits();
  const { buy, manage, busy, notice, waitForCredits } = useCheckout(credits);

  // Back from a full-page checkout (fallback when the popup redirects).
  useEffect(() => {
    if (params?.get("checkout") === "done" && params.get("status") !== "failed") void waitForCredits(credits);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const onBuy = (item: string) => {
    if (!isSignedIn) {
      router.push(`/sign-up?redirect_url=${encodeURIComponent("/pricing")}`);
      return;
    }
    if (item !== "free") void buy(item);
  };

  return (
    <PricingView
      credits={isSignedIn ? credits : null}
      signedIn={Boolean(isSignedIn)}
      busy={busy}
      notice={notice}
      onBuy={onBuy}
      onManage={manage}
    />
  );
}

export default function PricingPage() {
  return (
    <Suspense fallback={null}>
      <Pricing />
    </Suspense>
  );
}
