"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, BriefcaseBusiness, CalendarDays, MapPin, Search, SlidersHorizontal, X } from "lucide-react";

import { useApp } from "@/components/app-provider";
import { CompanyLogo } from "@/components/company-logo";
import { EmptyState, PageHeader } from "@/components/dashboard-view";
import { PageError } from "@/components/page-state";
import type { Job, JobBoardFilters, JobBoardSort, WorkMode } from "@/lib/api/types";

const TERMS = ["Fall 2026", "Winter 2027", "Summer 2027", "Fall 2027", "Winter 2028", "Summer 2028", "Fall 2028"];

export function JobsBoardView() {
  const { api } = useApp();
  const [items, setItems] = useState<Job[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [query, setQuery] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [term, setTerm] = useState("");
  const [workMode, setWorkMode] = useState<WorkMode>("any");
  const [postedWithinDays, setPostedWithinDays] = useState<"" | 1 | 7 | 14 | 30>("");
  const [sort, setSort] = useState<JobBoardSort>("newest");
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
      const filters: JobBoardFilters = {
        query: searchQuery || undefined,
        company: company.trim() || undefined,
        location: location.trim() || undefined,
        term: term || undefined,
        work_mode: workMode === "any" ? undefined : workMode,
        posted_within_days: postedWithinDays || undefined,
        sort,
      };
      const page = await api.jobs(next, filters);
      if (version !== loadVersion.current) return;
      setItems((current) => next ? [...current, ...page.items] : page.items);
      setCursor(page.next_cursor);
      setTotalCount(page.total_count);
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
  }, [api, company, location, postedWithinDays, searchQuery, sort, term, workMode]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (error && !items.length) return <PageError message={error} retry={() => void load()} />;

  const hasFilters = Boolean(searchQuery || company || location || term || workMode !== "any" || postedWithinDays || sort !== "newest");
  const clearFilters = () => {
    setQuery(""); setSearchQuery(""); setCompany(""); setLocation(""); setTerm("");
    setWorkMode("any"); setPostedWithinDays(""); setSort("newest");
  };

  return <div className="app-page jobs-board">
    <PageHeader
      eyebrow="All opportunities"
      title="Job board"
      copy="Browse active internships across Sprintern, then use filters to narrow the board to what matters to you."
    />
    <section className="board-filter-panel" aria-label="Job board filters">
      <div className="board-toolbar">
        <label>
          <Search size={18} />
          <span className="sr-only">Search jobs</span>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value.slice(0, 120))} placeholder="Search title, company, or location" />
        </label>
        <span>{loading ? "Checking the board…" : `${totalCount.toLocaleString()} role${totalCount === 1 ? "" : "s"} found`}</span>
      </div>
      <div className="board-filter-grid">
        <label><span>Company</span><input value={company} onChange={(event) => setCompany(event.target.value.slice(0, 120))} placeholder="Any company" /></label>
        <label><span>Location</span><input value={location} onChange={(event) => setLocation(event.target.value.slice(0, 120))} placeholder="Any location" /></label>
        <label><span>Term</span><select value={term} onChange={(event) => setTerm(event.target.value)}>
          <option value="">Any term</option>{TERMS.map((value) => <option value={value} key={value}>{value}</option>)}
        </select></label>
        <label><span>Work mode</span><select value={workMode} onChange={(event) => setWorkMode(event.target.value as WorkMode)}>
          <option value="any">Any mode</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option>
        </select></label>
        <label><span>Added</span><select value={postedWithinDays} onChange={(event) => setPostedWithinDays(event.target.value ? Number(event.target.value) as 1 | 7 | 14 | 30 : "")}>
          <option value="">Any time</option><option value={1}>Past 24 hours</option><option value={7}>Past week</option><option value={14}>Past 2 weeks</option><option value={30}>Past 30 days</option>
        </select></label>
        <label><span>Sort</span><select value={sort} onChange={(event) => setSort(event.target.value as JobBoardSort)}>
          <option value="newest">Newest</option><option value="relevance">Relevance</option><option value="company">Company</option><option value="deadline">Deadline</option>
        </select></label>
      </div>
      <div className="board-filter-footer">
        <span><SlidersHorizontal size={15} /> Filters update the board automatically.</span>
        {hasFilters && <button className="board-clear-filters" type="button" onClick={clearFilters}><X size={15} /> Clear filters</button>}
      </div>
    </section>

    {loading ? <BoardSkeleton /> : items.length ? <div className="board-list">
      {items.map((job) => <JobBoardRow job={job} key={job.id} />)}
    </div> : <EmptyState
      icon={<Search />}
      title={hasFilters ? "No roles match those filters" : "No current roles yet"}
      copy={hasFilters ? "Try clearing a filter or broadening your search." : "The board will fill as the next source checks finish."}
    />}

    {error && items.length > 0 && <p className="board-inline-error" role="status">{error}</p>}
    {cursor && <button className="button button--ghost board-load-more" disabled={loadingMore} onClick={() => void load(cursor)}>
      {loadingMore ? "Loading…" : `Load more roles (${items.length} of ${totalCount.toLocaleString()})`}
    </button>}
  </div>;
}

function JobBoardRow({ job }: { job: Job }) {
  const publishedAt = job.posted_at ?? job.first_seen_at;
  return <article className="board-job">
    <CompanyLogo company={job.company} size="large" />
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
  return `${Math.floor(seconds / 86400)}d ago`;
}
