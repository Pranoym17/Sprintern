import { notFound } from "next/navigation";
import { PublicJob } from "@/components/public-job";
import type { Job } from "@/lib/api/types";

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const base = process.env.PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010";
  const response = await fetch(`${base}/public/jobs/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (!response.ok) notFound();
  const payload = await response.json() as { job: Job };
  return <PublicJob job={payload.job} />;
}
