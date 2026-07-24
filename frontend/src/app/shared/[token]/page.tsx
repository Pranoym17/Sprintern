import { notFound } from "next/navigation";
import { PublicJob } from "@/components/public-job";
import type { Job } from "@/lib/api/types";

export default async function SharedJobPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const base = process.env.PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010/api/v1";
  const response = await fetch(`${base}/shared/jobs/${encodeURIComponent(token)}`, { cache: "no-store" });
  if (!response.ok) notFound();
  const payload = await response.json() as { job: Job; shared_until: string };
  return <PublicJob job={payload.job} expiresAt={payload.shared_until} />;
}
