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
  // Let the SDK redirect: Indian cards and 3-D Secure send the buyer to their bank to approve, then back to
  // our return URL (/pricing?checkout=done), which waits for the credits. With manualRedirect the bank step
  // never opened and the payment sat at "Processing" (Nov 13).
  DodoPayments.Checkout.open({ checkoutUrl, options: { showTimer: false } });
}

export async function closeCheckout() {
  const { DodoPayments } = await import("dodopayments-checkout");
  try {
    DodoPayments.Checkout.close();
  } catch {
    // already closed
  }
}
