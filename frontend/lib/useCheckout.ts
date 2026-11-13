"use client";

import { useCallback, useRef, useState } from "react";
import { useApi } from "@/lib/api";
import { openCheckout } from "@/lib/checkout";
import { type Credits, creditsStore } from "@/lib/credits";

export type Notice = { tone: "info" | "good" | "bad"; text: string } | null;

const POLL_MS = 2000;
const POLL_TRIES = 20; // ~40 s for Dodo's webhook to reach us

const title = (plan: string) => plan[0].toUpperCase() + plan.slice(1);

function errorText(err: unknown, fallback: string) {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

/** Buying a plan or pack (Dodo's one-page checkout in a popup), opening the billing portal, and waiting for
 * the payment to show up as credits. Shared by the pricing page and the usage panel. */
export function useCheckout(credits: Credits | null, onDone?: () => void) {
  const api = useApi();
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const polling = useRef(false);

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
            setNotice({ tone: "good", text: now.plan !== before?.plan ? `You're on ${title(now.plan)}.` : "Credits added." });
            onDone?.();
            polling.current = false;
            return;
          }
        } catch {
          // keep trying
        }
      }
      setNotice({ tone: "info", text: "Your payment went through. Credits can take a minute to show." });
      polling.current = false;
    },
    [api, onDone],
  );

  const buy = useCallback(
    async (item: string) => {
      setBusy(item);
      setNotice(null);
      const before = credits;
      try {
        const res = (await api("/api/billing/checkout", { method: "POST", data: { item } })).data as
          | { checkout_url: string; mode: "test" | "live" }
          | { changed: true; effective: "now" | "next_billing_date"; plan: string };
        if ("changed" in res) {
          if (res.effective === "now") void waitForCredits(before);
          else setNotice({ tone: "good", text: `You'll move to ${title(res.plan)} at your next billing date.` });
          return;
        }
        await openCheckout(res.checkout_url, res.mode, (e) => {
          if (e.event_type === "checkout.status") {
            // The SDK sends { message: { status } } (docs show { status }); accept both.
            const data = (e.data ?? {}) as { status?: unknown; message?: { status?: unknown } };
            const status = String(data.message?.status ?? data.status ?? "");
            if (["succeeded", "active"].includes(status)) {
              // Paid without a bank step: the SDK now redirects to /pricing?checkout=done, which waits for credits.
              void waitForCredits(before);
            } else if (status && status !== "processing" && status !== "requires_customer_action") {
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
    },
    [api, credits, waitForCredits],
  );

  const manage = useCallback(async () => {
    setBusy("portal");
    try {
      const { url } = (await api("/api/billing/portal", { method: "POST" })).data as { url: string };
      window.open(url, "_blank", "noopener");
    } catch (err) {
      setNotice({ tone: "bad", text: errorText(err, "Couldn't open billing settings. Try again in a minute.") });
    } finally {
      setBusy(null);
    }
  }, [api]);

  return { buy, manage, busy, notice, setNotice, waitForCredits };
}
