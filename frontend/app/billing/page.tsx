"use client";

import { useEffect, useState } from "react";
import { BillingView, type Entry } from "@/components/billing/BillingView";
import { useApi } from "@/lib/api";
import { useCredits } from "@/lib/credits";

export default function BillingPage() {
  const api = useApi();
  const credits = useCredits();
  const [history, setHistory] = useState<Entry[] | null>(null);

  useEffect(() => {
    api("/api/billing/history")
      .then((r) => setHistory((r.data as { entries: Entry[] }).entries))
      .catch(() => setHistory([]));
  }, [api]);

  return <BillingView credits={credits} history={history} />;
}
