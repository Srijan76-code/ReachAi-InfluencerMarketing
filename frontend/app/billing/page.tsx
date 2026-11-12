"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { BillingView, type Entry, type Notice } from "@/components/billing/BillingView";
import { useApi } from "@/lib/api";
import { type Credits, creditsStore, useCredits } from "@/lib/credits";
import { closeCheckout, openCheckout } from "@/lib/checkout";

const POLL_MS = 2000;
const POLL_TRIES = 20; // ~40 s for the payment provider's webhook to arrive

function errorText(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function Billing() {
  const api = useApi();
  const credits = useCredits();
  const params = useSearchParams();
  const [history, setHistory] = useState<Entry[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const polling = useRef(false);

  const loadHistory = useCallback(() => {
    api("/api/billing/history")
      .then((r) => setHistory((r.data as { entries: Entry[] }).entries))
      .catch(() => setHistory([]));
  }, [api]);

  useEffect(loadHistory, [loadHistory]);

  /** After paying, wait for the payment to reach our backend, then show the new plan or credits. */
  const waitForCredits = useCallback(
    async (before: Credits | null) => {
      if (polling.current) return;
      polling.current = true;
      setNotice({ tone: "info", text: "Payment received. Adding your credits…" });
      for (let i = 0; i < POLL_TRIES; i++) {
        await new Promise((r) => setTimeout(r, POLL_MS));
        try {
          const now = (await api("/api/billing/balance")).data as Credits;
          creditsStore.set(now);
          if (!before || now.balance !== before.balance || now.plan !== before.plan) {
            setNotice({ tone: "good", text: now.plan !== before?.plan ? `You're on ${now.plan[0].toUpperCase()}${now.plan.slice(1)}.` : "Credits added." });
            loadHistory();
            polling.current = false;
            return;
          }
        } catch {
          // keep trying
        }
      }
      setNotice({ tone: "info", text: "Your payment went through. Credits can take a minute to show; refresh this page soon." });
      polling.current = false;
    },
    [api, loadHistory],
  );

  // Coming back from a full-page checkout (fallback when the popup redirects).
  useEffect(() => {
    if (params?.get("checkout") === "done" && params.get("status") !== "failed") void waitForCredits(credits);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const buy = async (item: string) => {
    setBusy(item);
    setNotice(null);
    const before = credits;
    try {
      const res = (await api("/api/billing/checkout", { method: "POST", data: { item } })).data as
        | { checkout_url: string; mode: "test" | "live" }
        | { changed: true; effective: "now" | "next_billing_date"; plan: string };
      if ("changed" in res) {
        if (res.effective === "now") void waitForCredits(before);
        else setNotice({ tone: "good", text: `You'll move to ${res.plan[0].toUpperCase()}${res.plan.slice(1)} at your next billing date.` });
        return;
      }
      await openCheckout(res.checkout_url, res.mode, (e) => {
        if (e.event_type === "checkout.status") {
          // The SDK sends { message: { status } } (docs show { status }); accept both.
          const data = (e.data ?? {}) as { status?: unknown; message?: { status?: unknown } };
          const status = String(data.message?.status ?? data.status ?? "");
          if (["succeeded", "processing", "active"].includes(status)) {
            void closeCheckout();
            void waitForCredits(before);
          } else if (status) {
            setNotice({ tone: "bad", text: "The payment didn't go through. Nothing was charged; you can try again." });
          }
        }
        if (e.event_type === "checkout.error") setNotice({ tone: "bad", text: "Checkout hit a problem. Try again in a minute." });
      });
    } catch (err) {
      setNotice({ tone: "bad", text: errorText(err, "Couldn't open checkout. Try again in a minute.") });
    } finally {
      setBusy(null);
    }
  };

  const manage = async () => {
    setBusy("portal");
    try {
      const { url } = (await api("/api/billing/portal", { method: "POST" })).data as { url: string };
      window.open(url, "_blank", "noopener");
    } catch (err) {
      setNotice({ tone: "bad", text: errorText(err, "Couldn't open billing settings. Try again in a minute.") });
    } finally {
      setBusy(null);
    }
  };

  return <BillingView credits={credits} history={history} busy={busy} notice={notice} onBuy={buy} onManage={manage} />;
}

export default function BillingPage() {
  return (
    <Suspense fallback={null}>
      <Billing />
    </Suspense>
  );
}
