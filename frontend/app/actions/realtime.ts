"use server";

import { auth } from "@clerk/nextjs/server";
import { getClientSubscriptionToken } from "inngest/react";

import { inngest } from "@/inngest/client";
import { campaignChannel, outreachChannel } from "@/inngest/channels";

const backendUrl =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  "http://localhost:8000";

export async function getCampaignRealtimeToken(
  campaignId: string,
  runId: string,
) {
  const session = await auth();
  if (!session.userId) {
    throw new Error("Authentication required");
  }

  const token = await session.getToken();
  const response = await fetch(
    `${backendUrl}/api/campaigns/${campaignId}/status`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Campaign access denied");
  }

  const status = (await response.json()) as { run_id?: string };
  if (status.run_id !== runId) {
    throw new Error("Realtime run does not belong to this campaign");
  }

  return getClientSubscriptionToken(inngest, {
    channel: campaignChannel({ runId }),
    topics: ["status"],
  });
}

export async function getOutreachRealtimeToken(
  outreachJobId: string,
  runId: string,
) {
  const session = await auth();
  if (!session.userId) {
    throw new Error("Authentication required");
  }

  const token = await session.getToken();
  const response = await fetch(
    `${backendUrl}/api/outreach/jobs/${outreachJobId}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Outreach job access denied");
  }

  const job = (await response.json()) as { run_id?: string };
  if (job.run_id !== runId) {
    throw new Error("Realtime run does not belong to this outreach job");
  }

  return getClientSubscriptionToken(inngest, {
    channel: outreachChannel({ runId }),
    topics: ["status"],
  });
}
