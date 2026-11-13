import { redirect } from "next/navigation";

/** Billing moved: plans live on /pricing, your credits and history in the "Billing and usage" panel. */
export default function BillingPage() {
  redirect("/pricing");
}
