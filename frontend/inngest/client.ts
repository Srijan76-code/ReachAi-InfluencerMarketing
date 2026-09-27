import { Inngest } from "inngest";

const isDevelopment = process.env.NODE_ENV !== "production";
const localSigningKey = `signkey-dev-${"0".repeat(64)}`;

export const inngest = new Inngest({
  id: process.env.INNGEST_APP_ID ?? "reach-ai",
  baseUrl:
    process.env.INNGEST_BASE_URL ??
    (isDevelopment ? "http://127.0.0.1:8288" : undefined),
  signingKey:
    process.env.INNGEST_SIGNING_KEY ??
    (isDevelopment ? localSigningKey : undefined),
});
