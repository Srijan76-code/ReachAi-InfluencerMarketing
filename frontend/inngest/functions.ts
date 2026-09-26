import { inngest } from "./client";
import { campaignChannel, CampaignStageUpdate } from "./channels";

export const publishCampaignStage = inngest.createFunction(
  { id: "publish-campaign-stage", triggers: [{ event: "campaign/stage" }] },
  async ({ event, step }) => {
    const update = event.data as CampaignStageUpdate;
    const channel = campaignChannel({ runId: update.run_id });

    await step.realtime.publish("campaign-stage", channel.status, update);
    return { runId: update.run_id, stage: update.stage, status: update.status };
  },
);
