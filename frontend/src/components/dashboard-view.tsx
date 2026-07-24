"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, BellRing, CheckCircle2, Clock3, Filter, Radio, Send } from "lucide-react";

import { useApp } from "./app-provider";
import { PageError, PageLoading } from "./page-state";
import type { Analytics, JobFilter, JobMatch, Profile, SourceHealth } from "@/lib/api/types";

type DashboardData = { profile:Profile; filters:JobFilter[]; matches:JobMatch[]; analytics:Analytics; sourceHealth:SourceHealth };

export function DashboardView() {
  const { api } = useApp(); const [data, setData] = useState<DashboardData | null>(null); const [error, setError] = useState("");
  const load = useCallback(async () => { setError(""); try { const [profile, filters, page, analytics, sourceHealth] = await Promise.all([api.profile(), api.filters(), api.matches(), api.analytics(), api.sourceHealth()]); setData({ profile, filters, matches:page.items.slice(0, 4), analytics, sourceHealth }); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load your dashboard."); } }, [api]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  if (error) return <PageError message={error} retry={load}/>; if (!data) return <PageLoading/>;
  const activeFilters = data.filters.filter((filter) => filter.active).length; const ready = activeFilters > 0 && (data.profile.telegram_notifications_enabled || data.profile.email_notifications_enabled);
  return <div className="app-page"><PageHeader eyebrow="Overview" title="Your internship signal" copy="A quick read on what Sprintern has found and what needs your attention."/>
    {data.sourceHealth.state === "stale" && <div className="source-warning" role="status"><AlertTriangle size={19}/><span><strong>Job updates are delayed</strong><small>Existing matches remain available while Sprintern catches up.</small></span></div>}
    <section className="readiness-card"><div><span className={`readiness-icon ${ready?"ready":""}`}>{ready?<CheckCircle2/>:<BellRing/>}</span><span><strong>{ready?"Your alert is active":"Finish setting up your alert"}</strong><small>{ready?`${activeFilters} active filter${activeFilters===1?"":"s"} watching for new roles.`:"Create a filter and enable a notification channel."}</small></span></div><Link className="button button--dark button--small" href={ready?"/settings":"/onboarding"}>{ready?"Check settings":"Continue setup"}<ArrowRight size={16}/></Link></section>
    <section className="metric-grid"><Metric icon={<BellRing/>} label="Matches" value={data.analytics.matched_count}/><Metric icon={<Send/>} label="Applied" value={data.analytics.applied_count}/><Metric icon={<Clock3/>} label="Avg. time to apply" value={formatDuration(data.analytics.average_seconds_to_apply)}/><Metric icon={<Radio/>} label="Jobs checked" value={freshness(data.sourceHealth)}/></section>
    <section className="content-panel"><div className="panel-heading"><div><span className="page-eyebrow">Recent matches</span><h2>Ready for review</h2></div><Link href="/matches">View all <ArrowRight size={16}/></Link></div>{data.matches.length?<div className="compact-jobs">{data.matches.map((match)=><Link href={`/matches#${match.id}`} key={match.id}><span className="company-avatar">{match.job.company.slice(0,2).toUpperCase()}</span><span><strong>{match.job.title}</strong><small>{match.job.company} · {match.job.location??"Location not listed"}</small></span><span className={`status-pill status-pill--${match.status}`}>{match.status}</span></Link>)}</div>:<EmptyState icon={<Filter/>} title="No matches yet" copy={data.filters.length?"Your active filters have not found a role yet. Sprintern is still watching.":"Create a filter so Sprintern knows what to look for."} action="/filters" actionLabel="Manage filters"/>}</section>
  </div>;
}

export function PageHeader({eyebrow,title,copy,action}:{eyebrow:string;title:string;copy:string;action?:React.ReactNode}){return <header className="app-page-header"><div><span className="page-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{copy}</p></div>{action}</header>}
function Metric({icon,label,value}:{icon:React.ReactNode;label:string;value:string|number}){return <article className="metric-card"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></article>}
export function EmptyState({icon,title,copy,action,actionLabel}:{icon:React.ReactNode;title:string;copy:string;action?:string;actionLabel?:string}){return <div className="empty-state"><span>{icon}</span><h3>{title}</h3><p>{copy}</p>{action&&<Link className="button button--ghost button--small" href={action}>{actionLabel}<ArrowRight size={16}/></Link>}</div>}
function formatDuration(seconds:number|null){if(seconds===null)return "—";if(seconds<3600)return `${Math.max(1,Math.round(seconds/60))}m`;if(seconds<86400)return `${Math.round(seconds/3600)}h`;return `${Math.round(seconds/86400)}d`}
function freshness(health:SourceHealth){if(health.state==="unknown"||!health.last_updated_at)return "Waiting";const seconds=Math.max(0,(Date.now()-new Date(health.last_updated_at).getTime())/1000);if(seconds<3600)return `${Math.max(1,Math.floor(seconds/60))}m ago`;if(seconds<86400)return `${Math.floor(seconds/3600)}h ago`;return `${Math.floor(seconds/86400)}d ago`}
