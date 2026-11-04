import { redirect } from "next/navigation";

// The old "Saved" page: saved creators now live in the Shortlist view of the Creators tab.
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/campaign/${id}/leads?view=shortlist`);
}
