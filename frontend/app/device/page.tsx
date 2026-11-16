import type { Metadata } from "next";
import DeviceApproval from "./DeviceApproval";

export const metadata: Metadata = { title: "Connect an agent" };

export default async function DevicePage({ searchParams }: { searchParams: Promise<{ code?: string }> }) {
  const { code } = await searchParams;
  return <DeviceApproval initialCode={typeof code === "string" ? code.slice(0, 20) : ""} />;
}
