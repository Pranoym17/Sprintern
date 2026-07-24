import { ArrowUpRight, BriefcaseBusiness, Clock3, MapPin } from "lucide-react";
import Link from "next/link";

import type { Job } from "@/lib/api/types";
import { Brand } from "./brand";

export function PublicJob({ job, expiresAt }: { job: Job; expiresAt?: string | null }) {
  const applyUrl = job.application_url;
  return <main className="public-job-page">
    <header><Brand /><Link href="/">Back to Sprintern</Link></header>
    <article>
      <span className="page-eyebrow">Shared internship</span>
      <p className="public-job-company">{job.company}</p><h1>{job.title}</h1>
      <div className="job-meta">
        <span><MapPin size={17} />{job.location ?? "Location not listed"}</span>
        <span><BriefcaseBusiness size={17} />{job.term ?? "Term unknown"}</span>
        {job.deadline_at && <span><Clock3 size={17} />Deadline {new Date(job.deadline_at).toLocaleDateString()}</span>}
      </div>
      {job.title_incomplete && <p className="quality-warning">The title information may be incomplete.</p>}
      {job.description && <p className="public-job-description">{job.description}</p>}
      {applyUrl && <a className="button button--primary" href={applyUrl} target="_blank" rel="noopener noreferrer">Apply at employer <ArrowUpRight size={17} /></a>}
      {expiresAt && <small>This private link expires {new Date(expiresAt).toLocaleString()}.</small>}
    </article>
  </main>;
}
