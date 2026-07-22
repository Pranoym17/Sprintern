"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import {
  ArrowUpRight, Bookmark, BriefcaseBusiness, Check, ChevronDown, Clock3, Copy,
  EyeOff, Flag, MapPin, RotateCcw, Search, Share2, X,
} from "lucide-react";

import { useApp } from "./app-provider";
import { EmptyState, PageHeader } from "./dashboard-view";
import { MatchesSkeleton, PageError } from "./page-state";
import type {
  Collection, Job, JobInteraction, JobMatch, MatchCounts, MatchSort, MatchStatus,
} from "@/lib/api/types";

const tabs: ["all" | MatchStatus, string][] = [
  ["all", "All"], ["matched", "New"], ["applied", "Applied"], ["dismissed", "Dismissed"],
];
const seenStorageKey = "sprintern.seen-match-ids";
const collections: [Collection, string][] = [
  ["toronto", "Toronto internships"], ["remote", "Remote internships"],
  ["canadian", "Canadian internships"], ["new-week", "New this week"],
  ["closing-soon", "Closing soon"], ["reopened", "Recently reopened"],
  ["followed-companies", "Companies you follow"], ["strongest", "Strongest matches"],
  ["recently-viewed", "Recently viewed"],
];

export function MatchesView() {
  const { api, notify } = useApp();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [items, setItems] = useState<JobMatch[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [counts, setCounts] = useState<MatchCounts>({ all: 0, matched: 0, applied: 0, dismissed: 0 });
  const [tab, setTab] = useState<"all" | MatchStatus>("all");
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const [undo, setUndo] = useState<{ item: JobMatch; previous: MatchStatus } | null>(null);
  const [hiddenUndo, setHiddenUndo] = useState<JobMatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState(searchParams?.get("q") ?? "");
  const [sort, setSort] = useState<MatchSort>(validSort(searchParams?.get("sort") ?? null));
  const [collection, setCollection] = useState<Collection | undefined>(validCollection(searchParams?.get("collection") ?? null));
  const [interactions, setInteractions] = useState<Record<string, JobInteraction>>({});
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [similar, setSimilar] = useState<{ owner: string; jobs: Job[] } | null>(null);

  const load = useCallback(async (next?: string) => {
    setError("");
    if (next) setLoadingMore(true);
    try {
      const page = await api.matches(next, tab === "all" ? undefined : tab, query, sort, collection);
      setItems((current) => next ? [...current, ...page.items] : page.items);
      setCursor(page.next_cursor); setCounts(page.counts);
      const seen = readSeenMatches();
      setNewIds((current) => new Set([...current, ...page.items.filter((item) => !seen.has(item.id)).map((item) => item.id)]));
      writeSeenMatches(new Set([...seen, ...page.items.map((item) => item.id)]));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load matches.");
    } finally { setLoading(false); setLoadingMore(false); }
  }, [api, collection, query, sort, tab]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (sort !== "newest") params.set("sort", sort);
    if (collection) params.set("collection", collection);
    window.history.replaceState(null, "", `${pathname ?? "/matches"}${params.size ? `?${params}` : ""}`);
    const timer = window.setTimeout(() => {
      setLoading(true); setItems([]); setCursor(null); void load();
    }, 300);
    return () => window.clearTimeout(timer);
  }, [collection, load, pathname, query, sort, tab]);

  useEffect(() => {
    void api.interactions().then((values) =>
      setInteractions(Object.fromEntries(values.map((item) => [item.job_id, item]))),
    );
  }, [api]);

  const shown = useMemo(
    () => tab === "all" ? items : items.filter((item) => item.status === tab),
    [items, tab],
  );

  async function change(item: JobMatch, status: MatchStatus, offerUndo = false) {
    if (pendingIds.has(item.id)) return;
    const previous = item.status;
    setPendingIds((current) => new Set(current).add(item.id));
    setItems((current) => current.map((match) => match.id === item.id ? { ...match, status } : match));
    try {
      const updated = await api.updateMatch(item.id, status);
      setItems((current) => tab !== "all" && status !== tab
        ? current.filter((match) => match.id !== item.id)
        : current.map((match) => match.id === item.id ? updated : match));
      setCounts((current) => ({ ...current, [previous]: Math.max(0, current[previous] - 1), [status]: current[status] + 1 }));
      if (offerUndo) setUndo({ item: updated, previous });
      notify(status === "applied" ? "Marked as applied." : status === "dismissed" ? "Match dismissed." : "Match restored.");
    } catch (reason) {
      setItems((current) => current.map((match) => match.id === item.id ? { ...match, status: previous } : match));
      notify(reason instanceof Error ? reason.message : "Update failed.", "error");
    } finally {
      setPendingIds((current) => { const next = new Set(current); next.delete(item.id); return next; });
    }
  }

  async function interact(item: JobMatch, value: Record<string, unknown>) {
    try {
      const updated = await api.updateInteraction(item.job.id, value);
      setInteractions((current) => ({ ...current, [item.job.id]: updated }));
      if (value.hidden) {
        setItems((current) => current.filter((match) => match.id !== item.id));
        setHiddenUndo(item);
      } else if (value.hidden === false) {
        setItems((current) => current.some((match) => match.id === item.id) ? current : [item, ...current]);
      }
      notify(value.bookmarked ? "Job saved." : value.hidden ? "Job hidden." : "Job updated.");
    } catch (reason) { notify(reason instanceof Error ? reason.message : "Could not update job.", "error"); }
  }

  async function copyApplication(item: JobMatch) {
    const url = item.job.sources.find((source) => source.apply_url)?.apply_url;
    if (!url) return;
    await navigator.clipboard.writeText(url); notify("Application link copied.");
  }

  async function share(item: JobMatch) {
    try {
      const link = await api.shareJob(item.job.id);
      await navigator.clipboard.writeText(link.url); notify("Private 72-hour share link copied.");
    } catch (reason) { notify(reason instanceof Error ? reason.message : "Could not share job.", "error"); }
  }

  function toggleCompare(id: string) {
    setCompareIds((current) => current.includes(id)
      ? current.filter((value) => value !== id)
      : current.length < 3 ? [...current, id] : current);
  }

  async function showSimilar(item: JobMatch) {
    try {
      setSimilar({ owner: item.job.title, jobs: await api.similarJobs(item.job.id) });
    } catch (reason) { notify(reason instanceof Error ? reason.message : "Could not load similar jobs.", "error"); }
  }

  if (loading) return <MatchesSkeleton />;
  if (error && !items.length) return <PageError message={error} retry={() => load()} />;

  return <div className="app-page matches-page">
    <PageHeader eyebrow="Matches" title="Roles worth your time" copy="Search, compare, save and act on the roles that clear your filters." />
    <div className="discovery-toolbar">
      <label className="search-field"><Search size={18} /><span className="sr-only">Search jobs</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, company or location" /></label>
      <select aria-label="Sort jobs" value={sort} onChange={(event) => setSort(event.target.value as MatchSort)}><option value="newest">Newest</option><option value="company">Company</option><option value="relevance">Relevance</option><option value="deadline">Deadline</option></select>
      <select aria-label="Job collection" value={collection ?? ""} onChange={(event) => setCollection((event.target.value || undefined) as Collection | undefined)}><option value="">All jobs</option>{collections.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
    </div>
    {undo && <div className="undo-banner" role="status"><span><Check size={18} />Moved to Applied</span><button onClick={() => { void change(undo.item, undo.previous); setUndo(null); }}>Undo</button><button aria-label="Dismiss message" onClick={() => setUndo(null)}><X size={16} /></button></div>}
    {hiddenUndo && <div className="undo-banner" role="status"><span><EyeOff size={18} />Job hidden</span><button onClick={() => { void interact(hiddenUndo, { hidden: false }); setHiddenUndo(null); }}>Undo</button><button aria-label="Dismiss message" onClick={() => setHiddenUndo(null)}><X size={16} /></button></div>}
    <div className="feed-toolbar"><div className="tabs" aria-label="Filter matches by status">{tabs.map(([value, label]) => <button aria-pressed={tab === value} className={tab === value ? "active" : ""} key={value} onClick={() => setTab(value)}>{label}<span>{counts[value]}</span></button>)}</div><small>Server totals</small></div>
    {shown.length ? <div className="job-list">{shown.map((item) => <JobCard key={item.id} item={item} isNew={newIds.has(item.id)} interaction={interactions[item.job.id]} pending={pendingIds.has(item.id)} compared={compareIds.includes(item.id)} compareFull={compareIds.length >= 3} onChange={change} onInteract={interact} onCopy={copyApplication} onShare={share} onSimilar={showSimilar} onView={() => { void api.recordView(item.job.id); }} onCompare={toggleCompare} onFlag={(reason) => { void api.reportJob(item.job.id, reason); notify("Thanks — posting flagged for review."); }} />)}</div>
      : <EmptyState icon={<BriefcaseBusiness />} title="No matching jobs" copy="Try a broader search or review your filters. Sprintern is still watching for new roles." action="/filters" actionLabel="Review filters" />}
    {compareIds.length >= 2 && <ComparePanel ids={compareIds} items={items} clear={() => setCompareIds([])} />}
    {similar && <section className="similar-panel"><div><span><strong>Similar to</strong> {similar.owner}</span><button onClick={() => setSimilar(null)}><X size={16} />Close</button></div>{similar.jobs.length ? <div>{similar.jobs.map((job) => <a href={`/jobs/${job.id}`} target="_blank" key={job.id}><small>{job.company}</small><strong>{job.title}</strong><span>{job.location ?? "Location unknown"}</span></a>)}</div> : <p>No close alternatives are currently in your matches.</p>}</section>}
    {cursor && <button className="button button--ghost load-more" disabled={loadingMore} onClick={() => load(cursor)}>{loadingMore ? "Loading…" : "Load more matches"}<ChevronDown size={17} /></button>}
  </div>;
}

type CardProps = {
  item: JobMatch; isNew: boolean; interaction?: JobInteraction; pending: boolean;
  compared: boolean; compareFull: boolean;
  onChange: (item: JobMatch, status: MatchStatus, undo?: boolean) => Promise<void>;
  onInteract: (item: JobMatch, value: Record<string, unknown>) => Promise<void>;
  onCopy: (item: JobMatch) => Promise<void>; onShare: (item: JobMatch) => Promise<void>;
  onSimilar: (item: JobMatch) => Promise<void>;
  onCompare: (id: string) => void; onView: () => void; onFlag: (reason: string) => void;
};

function JobCard({ item, isNew, interaction, pending, compared, compareFull, onChange, onInteract, onCopy, onShare, onSimilar, onCompare, onView, onFlag }: CardProps) {
  const applyUrl = item.job.sources.find((source) => source.apply_url)?.apply_url;
  const deadline = interaction?.deadline_override_at ?? item.job.deadline_at;
  return <article className={`job-card ${isNew ? "job-card--new" : ""} ${item.status === "applied" ? "job-card--applied" : ""}`} id={item.id}>
    <div className="job-card__top"><span className="company-avatar company-avatar--large">{item.job.company.slice(0, 2).toUpperCase()}</span><div className="job-card__identity"><div className="company-line"><p>{item.job.company}</p>{isNew && <span className="new-badge"><i />New</span>}</div><h2>{item.job.title}</h2>{item.job.title_incomplete && <small className="quality-warning">Title incomplete at source</small>}<div className="job-meta"><span><MapPin size={15} />{item.job.location ?? "Location not listed"}</span><span><BriefcaseBusiness size={15} />{item.job.term ?? "Term unknown"}</span><span><Clock3 size={15} />{relativeTime(item.job.posted_at ?? item.job.first_seen_at)}</span>{deadline && <span className={`deadline-badge ${deadlineUrgency(deadline)}`}><Clock3 size={15} />{deadlineLabel(deadline)}{interaction?.deadline_override_at ? " · your date" : item.job.deadline_source ? ` · ${item.job.deadline_source}` : ""}</span>}</div></div><span className={`status-pill status-pill--${item.status}`}>{item.status}</span></div>
    {item.reasons[0]?.dimensions && <div className="reason-row"><span>Matched on</span>{Object.values(item.reasons[0].dimensions).map((value) => <em key={value}>{value}</em>)}</div>}
    <div className="job-card__actions">{applyUrl ? <a className="button button--primary button--small" href={applyUrl} target="_blank" rel="noopener noreferrer" onClick={onView}>Apply now <ArrowUpRight size={16} /></a> : <span className="apply-unavailable">Application link unavailable</span>}{item.status !== "applied" && <button className="button apply-button button--small" disabled={pending} onClick={() => void onChange(item, "applied", true)}><Check size={16} />Mark applied</button>}{item.status === "matched" ? <button className="icon-text-button" disabled={pending} onClick={() => void onChange(item, "dismissed")}><X size={16} />Dismiss</button> : item.status === "dismissed" && <button className="icon-text-button" disabled={pending} onClick={() => void onChange(item, "matched")}><RotateCcw size={16} />Restore</button>}<button className={`icon-text-button ${interaction?.bookmarked_at ? "active" : ""}`} onClick={() => void onInteract(item, { bookmarked: !interaction?.bookmarked_at })}><Bookmark size={16} fill={interaction?.bookmarked_at ? "currentColor" : "none"} />Save</button><button className="icon-text-button" onClick={() => void onInteract(item, { hidden: true })}><EyeOff size={16} />Hide</button><button className="icon-text-button" onClick={() => void onCopy(item)}><Copy size={16} />Copy</button><button className="icon-text-button" onClick={() => void onShare(item)}><Share2 size={16} />Share</button><label className="compact-select"><select aria-label="Not interested reason" defaultValue="" onChange={(event) => { if (event.target.value) void onInteract(item, { not_interested_reason: event.target.value }); }}><option value="">Not interested…</option><option value="wrong_role">Wrong role</option><option value="wrong_location">Wrong location</option><option value="wrong_term">Wrong term</option><option value="authorization">Authorization</option><option value="unpaid">Unpaid</option><option value="not_internship">Not an internship</option><option value="company_preference">Company preference</option><option value="other">Other</option></select></label><label className="compact-select"><Flag size={15} /><select aria-label="Flag posting" defaultValue="" onChange={(event) => { if (event.target.value) onFlag(event.target.value); }}><option value="">Flag…</option><option value="closed">Closed</option><option value="duplicate">Duplicate</option><option value="suspicious">Suspicious</option><option value="inaccurate">Inaccurate data</option></select></label><label className="compare-check"><input type="checkbox" checked={compared} onChange={() => onCompare(item.id)} disabled={!compared && compareFull} />Compare</label></div>
    <div className="discovery-secondary"><label>Your deadline <input type="date" value={interaction?.deadline_override_at?.slice(0, 10) ?? ""} onChange={(event) => void onInteract(item, { deadline_override_at: event.target.value ? new Date(`${event.target.value}T23:59:59`).toISOString() : null })} /></label><button onClick={() => { void navigator.clipboard.writeText(`${window.location.origin}/jobs/${item.job.id}`); }}><Share2 size={15} />Copy public link</button><button onClick={() => void onSimilar(item)}>Show similar jobs</button></div>
  </article>;
}

function ComparePanel({ ids, items, clear }: { ids: string[]; items: JobMatch[]; clear: () => void }) {
  return <section className="compare-panel" aria-label="Job comparison">
    <div><strong>Compare {ids.length} jobs</strong><button onClick={clear}>Clear</button></div>
    <div className="compare-grid">{ids.map((id) => {
      const match = items.find((item) => item.id === id);
      const applyUrl = match?.job.sources.find((source) => source.apply_url)?.apply_url;
      return match ? <article key={id}>
        <p>{match.job.company}</p><h3>{match.job.title}</h3>
        <span>{match.job.location ?? "Unknown location"} · {match.job.work_mode}</span>
        <span>{match.job.term ?? "Unknown term"}</span>
        <span>Deadline: {match.job.deadline_at ? new Date(match.job.deadline_at).toLocaleDateString() : "Not listed"}</span>
        <span>Source refreshed {relativeTime(match.job.last_seen_at)}</span>
        <span>Match: {Object.values(match.reasons[0]?.dimensions ?? {}).join(", ") || "General fit"}</span>
        <span>Application: {match.status}</span>
        <span>Notes: none yet</span>
        {applyUrl && <a href={applyUrl} target="_blank" rel="noopener noreferrer">Original application <ArrowUpRight size={13} /></a>}
      </article> : null;
    })}</div>
  </section>;
}

function validSort(value: string | null): MatchSort { return ["newest", "company", "relevance", "deadline"].includes(value ?? "") ? value as MatchSort : "newest"; }
function validCollection(value: string | null): Collection | undefined { return collections.some(([item]) => item === value) ? value as Collection : undefined; }
function deadlineUrgency(value: string) { const days = (new Date(value).getTime() - Date.now()) / 86400000; return days < 0 ? "expired" : days <= 1 ? "urgent" : days <= 3 ? "soon" : days <= 7 ? "upcoming" : ""; }
function deadlineLabel(value: string) { const days = Math.ceil((new Date(value).getTime() - Date.now()) / 86400000); return days < 0 ? "Deadline passed" : days === 0 ? "Due today" : `${days}d left`; }
function readSeenMatches() { try { return new Set<string>(JSON.parse(window.localStorage.getItem(seenStorageKey) ?? "[]")); } catch { return new Set<string>(); } }
function writeSeenMatches(ids: Set<string>) { try { window.localStorage.setItem(seenStorageKey, JSON.stringify([...ids].slice(-500))); } catch { /* Storage may be unavailable. */ } }
function relativeTime(value: string) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); if (seconds < 60) return "just now"; if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`; if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`; const days = Math.floor(seconds / 86400); return days < 30 ? `${days}d ago` : `${Math.floor(days / 30)}mo ago`; }
