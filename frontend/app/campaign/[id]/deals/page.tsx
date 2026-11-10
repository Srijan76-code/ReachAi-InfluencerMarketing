import { redirect } from "next/navigation";

/** Deals moved into Outreach (Nov 5): old links and alerts still land in the right chat. */
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string>> }) {
  const { id } = await params;
  const q = new URLSearchParams(await searchParams).toString();
  redirect(`/campaign/${id}/outreach${q ? `?${q}` : ""}`);
}
