import { realtime, staticSchema } from "inngest";

export type CampaignStageUpdate = {
  run_id: string;
  thread_id: string;
  stage: string;
  status: "running" | "completed" | "failed";
  ts: number;
};

/** Creators scored so far, sent by the new discovery engine as each platform finishes judging. */
export type CampaignLeadsUpdate = {
  run_id: string;
  ts: number;
  platform?: string;
  items: {
    creator_id: string;
    display_name: string;
    final_score: number;
    deal_status: string;
    flags?: string[];
  }[];
};

export const campaignChannel = realtime.channel({
  name: ({ runId }: { runId: string }) => `campaign:${runId}`,
  topics: {
    status: {
      schema: staticSchema<CampaignStageUpdate>(),
    },
    leads: {
      schema: staticSchema<CampaignLeadsUpdate>(),
    },
  },
});

export type OutreachStageUpdate = {
  outreach_job_id: string;
  creator_id?: string;
  pitch_status?: string;
  stage: string;
  status: "running" | "completed" | "failed";
  completed_count?: number;
  total_count?: number;
  stats?: Record<string, any>;
  error?: string;
  ts: number;
};

export const outreachChannel = realtime.channel({
  name: ({ runId }: { runId: string }) => `outreach:${runId}`,
  topics: {
    status: {
      schema: staticSchema<OutreachStageUpdate>(),
    },
  },
});
