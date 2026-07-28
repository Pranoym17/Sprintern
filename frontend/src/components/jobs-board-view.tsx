"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, BriefcaseBusiness, CalendarDays, MapPin, Search } from "lucide-react";

import { useApp } from "@/components/app-provider";
import { EmptyState, PageHeader } from "@/components/dashboard-view";
import { PageError } from "@/components/page-state";
import type { Job } from "@/lib/api/types";

export function JobsBoardView() {
  const { api } = useApp();
  const [items, setItems] = useState<Job[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const loadVersion = useRef(0);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearchQuery(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  const load = useCallback(async (next?: string) => {
    const version = next ? loadVersion.current : ++loadVersion.current;
    setError("");
    if (next) setLoadingMore(true);
    else setLoading(true);
    try {
      const page = await api.jobs(next, searchQuery);
      if (version !== loadVersion.current) return;
      setItems((current) => next ? [...current, ...page.items] : page.items);
      setCursor(page.next_cursor);
    } catch (reason) {
      if (version === loadVersion.current) {
        setError(reason instanceof Error ? reason.message : "Could not load the job board.");
      }
    } finally {
      if (version === loadVersion.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [api, searchQuery]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (error && !items.length) return <PageError message={error} retry={() => void load()} />;

  return <div className="app-page jobs-board">
    <PageHeader
      eyebrow="All opportunities"
      title="The 30-day job board"
      copy="Browse every active internship Sprintern has found in the past 30 days. Your Matches page remains the personalized shortlist."
    />
    <div className="board-toolbar">
      <label>
        <Search size={18} />
        <span className="sr-only">Search jobs</span>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value.slice(0, 120))}
          placeholder="Search title, company, or location"
        />
      </label>
      <span>{loading ? "Checking the board…" : `${items.length} role${items.length === 1 ? "" : "s"} shown`}</span>
    </div>

    {loading ? <BoardSkeleton /> : items.length ? <div className="board-list">
      {items.map((job) => <JobBoardRow job={job} key={job.id} />)}
    </div> : <EmptyState
      icon={<Search />}
      title={searchQuery ? "No roles match that search" : "No current roles yet"}
      copy={searchQuery ? "Try a company, role, or location with fewer words." : "The board will fill as the next source checks finish."}
    />}

    {error && items.length > 0 && <p className="board-inline-error" role="status">{error}</p>}
    {cursor && <button className="button button--ghost board-load-more" disabled={loadingMore} onClick={() => void load(cursor)}>
      {loadingMore ? "Loading…" : "Load more roles"}
    </button>}
  </div>;
}

function JobBoardRow({ job }: { job: Job }) {
  const publishedAt = job.posted_at ?? job.first_seen_at;
  return <article className="board-job">
    <span className="company-avatar company-avatar--large" aria-hidden="true">{job.company.slice(0, 2).toUpperCase()}</span>
    <div className="board-job__identity">
      <p>{job.company}</p>
      <h2><Link href={`/jobs/${job.id}`}>{job.title}</Link></h2>
      <div className="job-meta">
        <span><MapPin size={15} />{job.location ?? "Location not listed"}</span>
        <span><BriefcaseBusiness size={15} />{job.term ?? "Term unknown"}</span>
        <span><CalendarDays size={15} /><time dateTime={publishedAt}>{relativeTime(publishedAt)}</time></span>
      </div>
    </div>
    <a className="button button--primary button--small board-job__apply" href={job.application_url} target="_blank" rel="noreferrer">
      Apply <ArrowUpRight size={16} />
    </a>
  </article>;
}

function BoardSkeleton() {
  return <div className="board-list board-list--loading" aria-busy="true" aria-label="Loading the job board">
    {[1, 2, 3, 4, 5].map((item) => <div className="board-job" key={item}>
      <span className="skeleton skeleton--avatar" />
      <div><span className="skeleton skeleton--line-short" /><span className="skeleton skeleton--line-title" /><span className="skeleton skeleton--line-long" /></div>
    </div>)}
  </div>;
}

function relativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "Just added";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  const days = Math.floor(seconds / 86400);
  return `${days}d ago`;
}
