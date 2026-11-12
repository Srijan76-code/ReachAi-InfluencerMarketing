"use client";

import type { CheckoutEvent } from "dodopayments-checkout";

/** Opens Dodo's payment popup over the current page (spec §5.4). The SDK is loaded only when needed and
 * initialised once per mode; each open gets its own event handler. */
let initialisedMode: string | null = null;
let handler: ((e: CheckoutEvent) => void) | null = null;

export async function openCheckout(checkoutUrl: string, mode: "test" | "live", onEvent: (e: CheckoutEvent) => void) {
  const { DodoPayments } = await import("dodopayments-checkout");
  handler = onEvent;
  if (initialisedMode !== mode) {
    DodoPayments.Initialize({ mode, displayType: "overlay", onEvent: (e) => handler?.(e) });
    initialisedMode = mode;
  }
  // manualRedirect: stay on the billing page after paying instead of reloading it.
  DodoPayments.Checkout.open({ checkoutUrl, options: { manualRedirect: true, showTimer: false } });
}

export async function closeCheckout() {
  const { DodoPayments } = await import("dodopayments-checkout");
  try {
    DodoPayments.Checkout.close();
  } catch {
    // already closed
  }
}
