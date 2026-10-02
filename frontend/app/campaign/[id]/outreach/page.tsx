import OutreachClient from "./OutreachClient";
import WorkflowStatus from "../WorkflowStatus";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ job_id?: string }>;
}) {
  const { id } = await params;
  const { job_id } = await searchParams;

  return (
    <div className="max-w-full overflow-x-hidden">
      {/* <WorkflowStatus campaignId={id} /> */}
      <OutreachClient campaignId={id} initialJobId={job_id} />
    </div>
  );
}
