"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  Clock3,
  MapPin,
  RotateCcw,
  X,
} from "lucide-react";

import { useApp } from "./app-provider";
import { EmptyState, PageHeader } from "./dashboard-view";
import { MatchesSkeleton, PageError } from "./page-state";
import type { JobMatch, MatchCounts, MatchStatus } from "@/lib/api/types";

const tabs: ["all" | MatchStatus, string][] = [
  ["all", "All"], ["matched", "New"], ["applied", "Applied"], ["dismissed", "Dismissed"],
];
const seenStorageKey = "sprintern.seen-match-ids";

export function MatchesView() {
  const { api, notify } = useApp();
  const [items, setItems] = useState<JobMatch[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [counts, setCounts] = useState<MatchCounts>({ all: 0, matched: 0, applied: 0, dismissed: 0 });
  const [tab, setTab] = useState<"all" | MatchStatus>("all");
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const [undo, setUndo] = useState<{ item: JobMatch; previous: MatchStatus } | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (next?: string, selected: "all" | MatchStatus = "all") => {
    setError("");
    if (next) setLoadingMore(true);
    try {
      const page = await api.matches(next, selected === "all" ? undefined : selected);
      setItems((current) => next ? [...current, ...page.items] : page.items);
      setCursor(page.next_cursor);
      setCounts(page.counts);
      const seen = readSeenMatches();
      setNewIds((current) => new Set([...current, ...page.items.filter((item) => !seen.has(item.id)).map((item) => item.id)]));
      writeSeenMatches(new Set([...seen, ...page.items.map((item) => item.id)]));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load matches.");
    } finally {
      setLoading(false); setLoadingMore(false);
    }
  }, [api]);

  async function selectTab(value: "all" | MatchStatus) {
    if (value === tab) return;
    setTab(value); setLoading(true); setItems([]); setCursor(null);
    await load(undefined, value);
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const shown = useMemo(() => tab === "all" ? items : items.filter((item) => item.status === tab), [items, tab]);

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

  if (loading) return <MatchesSkeleton />;
  if (error && !items.length) return <PageError message={error} retry={() => load()} />;

  return <div className="app-page matches-page">
    <PageHeader eyebrow="Matches" title="Roles worth your time" copy="Scan the essentials, see why each role matched, and apply at the original source." />
    {undo && <div className="undo-banner" role="status"><span><Check size={18} />Moved to Applied</span><button onClick={() => { void change(undo.item, undo.previous); setUndo(null); }}>Undo</button><button aria-label="Dismiss message" onClick={() => setUndo(null)}><X size={16} /></button></div>}
    <div className="feed-toolbar">
      <div className="tabs" aria-label="Filter loaded matches by status">
        {tabs.map(([value, label]) => <button aria-pressed={tab === value} className={tab === value ? "active" : ""} key={value} onClick={() => void selectTab(value)}>{label}<span>{counts[value]}</span></button>)}
      </div>
      <small>Server totals</small>
    </div>
    {shown.length ? <div className="job-list">{shown.map((item) => {
      const isNew = newIds.has(item.id);
      const applyUrl = item.job.sources.find((source) => source.apply_url)?.apply_url;
      return <article className={`job-card ${isNew ? "job-card--new" : ""} ${item.status === "applied" ? "job-card--applied" : ""}`} id={item.id} key={item.id}>
        <div className="job-card__top">
          <span className="company-avatar company-avatar--large">{item.job.company.slice(0, 2).toUpperCase()}</span>
          <div className="job-card__identity">
            <div className="company-line"><p>{item.job.company}</p>{isNew && <span className="new-badge"><i />New</span>}</div>
            <h2>{item.job.title}</h2>
            <div className="job-meta">
              <span><MapPin size={15} />{item.job.location ?? "Location not listed"}</span>
              <span><BriefcaseBusiness size={15} />{item.job.term ?? "Term unknown"}</span>
              <span><Clock3 size={15} />{relativeTime(item.job.posted_at ?? item.job.first_seen_at)}</span>
            </div>
          </div>
          <span className={`status-pill status-pill--${item.status}`}>{item.status}</span>
        </div>
        {item.reasons[0]?.dimensions && <div className="reason-row"><span>Matched on</span>{Object.values(item.reasons[0].dimensions).map((value) => <em key={value}>{value}</em>)}</div>}
        {!!item.deliveries?.length && <div className="delivery-row" aria-label="Notification delivery status">{item.deliveries.map((delivery)=><span className={`delivery-badge delivery-badge--${delivery.status}`} key={delivery.channel}>{delivery.channel} {delivery.status}</span>)}</div>}
        <div className="job-card__actions">
          {applyUrl ? <a className="button button--primary button--small" href={applyUrl} target="_blank" rel="noopener noreferrer">Apply now <ArrowUpRight size={16} /></a> : <span className="apply-unavailable">Application link unavailable</span>}
          {item.status !== "applied" && <button className="button apply-button button--small" disabled={pendingIds.has(item.id)} onClick={() => change(item, "applied", true)}><Check size={16} />Mark applied</button>}
          {item.status === "matched" ? <button className="icon-text-button" disabled={pendingIds.has(item.id)} onClick={() => change(item, "dismissed")}><X size={16} />Dismiss</button> : item.status === "dismissed" && <button className="icon-text-button" disabled={pendingIds.has(item.id)} onClick={() => change(item, "matched")}><RotateCcw size={16} />Restore</button>}
        </div>
      </article>;
    })}</div> : <EmptyState icon={<BriefcaseBusiness />} title={`No ${tab === "all" ? "" : tab} matches yet`} copy="Sprintern is actively watching GitHub repositories. You’ll be alerted as soon as a role clears your filters." action="/filters" actionLabel="Review filters" />}
    {cursor && <button className="button button--ghost load-more" disabled={loadingMore} onClick={() => load(cursor, tab)}>{loadingMore ? "Loading…" : "Load more matches"}<ChevronDown size={17} /></button>}
  </div>;
}

function readSeenMatches() {
  try { return new Set<string>(JSON.parse(window.localStorage.getItem(seenStorageKey) ?? "[]")); }
  catch { return new Set<string>(); }
}

function writeSeenMatches(ids: Set<string>) {
  try { window.localStorage.setItem(seenStorageKey, JSON.stringify([...ids].slice(-500))); }
  catch { /* Private browsing can deny storage; the feed remains functional. */ }
}

function relativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  const days = Math.floor(seconds / 86400);
  return days < 30 ? `${days}d ago` : `${Math.floor(days / 30)}mo ago`;
}
