import type { Metadata } from "next";
import GrantApproval from "./GrantApproval";

export const metadata: Metadata = { title: "Allow your agent" };

export default async function GrantPage({ searchParams }: { searchParams: Promise<{ code?: string }> }) {
  const { code } = await searchParams;
  return <GrantApproval initialCode={typeof code === "string" ? code.slice(0, 20) : ""} />;
}
