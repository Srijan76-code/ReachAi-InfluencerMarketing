import { realtime, staticSchema } from "inngest";

export type CampaignStageUpdate = {
  run_id: string;
  thread_id: string;
  stage: string;
  status: "running" | "completed" | "failed";
  ts: number;
};

export const campaignChannel = realtime.channel({
  name: ({ runId }: { runId: string }) => `campaign:${runId}`,
  topics: {
    status: {
      schema: staticSchema<CampaignStageUpdate>(),
    },
  },
});
