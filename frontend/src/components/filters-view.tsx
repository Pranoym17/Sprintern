"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Bell, Building2, Filter as FilterIcon, LoaderCircle, Pencil, Plus, Power, Trash2, X,
} from "lucide-react";

import { useApp } from "./app-provider";
import { EmptyState, PageHeader } from "./dashboard-view";
import { PageError, PageLoading } from "./page-state";
import type {
  CompanyWatchlist, FilterInput, FilterNotification, FilterPreview, JobFilter,
  NotificationCadence, WorkMode,
} from "@/lib/api/types";

const blank: FilterInput = {
  name: "", role_keywords: [], location_keywords: [], terms: [], work_mode: "any",
  active: true, remote_only: false, radius_km: null, center_latitude: null,
  center_longitude: null, excluded_keywords: [], excluded_companies: [],
  excluded_locations: [],
};
const termOptions = ["Fall 2026", "Winter 2027", "Summer 2027", "Fall 2027", "Winter 2028", "Summer 2028", "Fall 2028"];
const cities: Record<string, [number, number]> = {
  Toronto: [43.6532, -79.3832], Vancouver: [49.2827, -123.1207],
  Montreal: [45.5019, -73.5674], Ottawa: [45.4215, -75.6972],
  Calgary: [51.0447, -114.0719], Edmonton: [53.5461, -113.4938],
  Waterloo: [43.4643, -80.5204], Halifax: [44.6488, -63.5752],
};

export function FiltersView() {
  const { api, notify } = useApp();
  const [filters, setFilters] = useState<JobFilter[]>([]);
  const [watchlists, setWatchlists] = useState<CompanyWatchlist[]>([]);
  const [editing, setEditing] = useState<JobFilter | "new" | null>(null);
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [loadedFilters, loadedWatchlists] = await Promise.all([api.filters(), api.watchlists()]);
      setFilters(loadedFilters); setWatchlists(loadedWatchlists); setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load targeting controls."); }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  async function toggle(filter: JobFilter) {
    if (pendingIds.has(filter.id)) return;
    setPendingIds((current) => new Set(current).add(filter.id));
    try {
      const updated = await api.updateFilter(filter.id, { active: !filter.active });
      setFilters((current) => current.map((item) => item.id === filter.id ? updated : item));
      notify(updated.active ? "Filter activated." : "Filter paused.");
    } catch (reason) { notify(reason instanceof Error ? reason.message : "Update failed.", "error"); }
    finally { setPendingIds((current) => { const next = new Set(current); next.delete(filter.id); return next; }); }
  }

  async function remove(filter: JobFilter) {
    if (pendingIds.has(filter.id) || !window.confirm(`Delete “${filter.name}”? This cannot be undone.`)) return;
    setPendingIds((current) => new Set(current).add(filter.id));
    try { await api.deleteFilter(filter.id); setFilters((current) => current.filter((item) => item.id !== filter.id)); notify("Filter deleted."); }
    catch (reason) { notify(reason instanceof Error ? reason.message : "Delete failed.", "error"); }
  }

  if (loading) return <PageLoading label="Loading filters" />;
  if (error) return <PageError message={error} retry={load} />;

  return <div className="app-page">
    <PageHeader eyebrow="Filters" title="Tune your signal" copy="Preview exactly what passes before an alert is ever sent." action={<button className="button button--primary" onClick={() => setEditing("new")}><Plus size={18} />New filter</button>} />
    {editing && <FilterEditor initial={editing === "new" ? blank : editing} onCancel={() => setEditing(null)} onSaved={(value) => { setFilters((current) => editing === "new" ? [value, ...current] : current.map((item) => item.id === value.id ? value : item)); setEditing(null); }} />}
    {filters.length ? <div className="filter-list">{filters.map((filter) => <FilterCard key={filter.id} filter={filter} pending={pendingIds.has(filter.id)} edit={() => setEditing(filter)} toggle={() => void toggle(filter)} remove={() => void remove(filter)} />)}</div> : !editing && <EmptyState icon={<FilterIcon />} title="Create your first signal" copy="Add the roles, places and term you care about. Preview the results before saving." />}
    <WatchlistPanel values={watchlists} onChange={setWatchlists} />
  </div>;
}

function FilterCard({ filter, pending, edit, toggle, remove }: { filter: JobFilter; pending: boolean; edit: () => void; toggle: () => void; remove: () => void }) {
  const exclusions = (filter.exclusions ?? []).map((item) => item.value);
  return <article className={`filter-card ${filter.active ? "filter-card--active" : "filter-card--paused"}`}>
    <div className="filter-card__heading"><span className="feature-icon"><FilterIcon size={20} /></span><div><h2>{filter.name}</h2><span className={`status-pill ${filter.active ? "status-pill--matched" : ""}`}>{filter.active ? "Actively watching" : "Paused"}</span></div><div className="filter-card__controls"><button disabled={pending} onClick={edit} aria-label={`Edit ${filter.name}`}><Pencil size={18} /></button><button disabled={pending} onClick={toggle} aria-label={`${filter.active ? "Pause" : "Activate"} ${filter.name}`}><Power size={18} /></button><button disabled={pending} className="danger" onClick={remove} aria-label={`Delete ${filter.name}`}><Trash2 size={18} /></button></div></div>
    <dl className="filter-details"><div><dt>Roles</dt><dd>{filter.role_keywords.join(", ") || "Any role"}</dd></div><div><dt>Locations</dt><dd>{filter.remote_only ? "Remote only" : filter.location_keywords.join(", ") || "Any location"}</dd></div><div><dt>Term</dt><dd>{filter.terms.join(", ") || "Any term"}</dd></div><div><dt>Excluded</dt><dd>{exclusions.join(", ") || "Nothing"}</dd></div>{filter.radius_km && <div><dt>Radius</dt><dd>{filter.radius_km} km</dd></div>}</dl>
    <FilterRouting filterId={filter.id} />
  </article>;
}

function FilterRouting({ filterId }: { filterId: string }) {
  const { api, notify } = useApp();
  const [value, setValue] = useState<FilterNotification | null>(null);
  const [open, setOpen] = useState(false);
  async function toggleOpen() {
    const next = !open; setOpen(next);
    if (next && !value) {
      try { setValue(await api.filterNotifications(filterId)); }
      catch (reason) { notify(reason instanceof Error ? reason.message : "Could not load alert routing.", "error"); }
    }
  }
  async function save(next: FilterNotification) {
    setValue(next);
    try {
      setValue(await api.updateFilterNotifications(filterId, {
        email_enabled: next.email_enabled,
        telegram_enabled: next.telegram_enabled,
        cadence: next.cadence,
        priority: next.priority,
      }));
      notify("Filter alert routing saved.");
    } catch (reason) { notify(reason instanceof Error ? reason.message : "Could not save routing.", "error"); }
  }
  return <div className="filter-routing">
    <button type="button" onClick={() => void toggleOpen()}><Bell size={15} />Alert routing</button>
    {open && value && <div>
      <label>Email<select value={String(value.email_enabled)} onChange={(event) => void save({ ...value, email_enabled: event.target.value === "null" ? null : event.target.value === "true" })}><option value="null">Profile default</option><option value="true">On</option><option value="false">Off</option></select></label>
      <label>Telegram<select value={String(value.telegram_enabled)} onChange={(event) => void save({ ...value, telegram_enabled: event.target.value === "null" ? null : event.target.value === "true" })}><option value="null">Profile default</option><option value="true">On</option><option value="false">Off</option></select></label>
      <label>Cadence<select value={value.cadence ?? ""} onChange={(event) => void save({ ...value, cadence: (event.target.value || null) as NotificationCadence | null })}><option value="">Profile default</option>{["instant", "hourly", "daily", "weekly"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Priority<select value={value.priority} onChange={(event) => void save({ ...value, priority: event.target.value as "normal" | "high" })}><option value="normal">Normal</option><option value="high">High</option></select></label>
    </div>}
  </div>;
}

function FilterEditor({ initial, onCancel, onSaved }: { initial: FilterInput | JobFilter; onCancel: () => void; onSaved: (value: JobFilter) => void }) {
  const { api, notify } = useApp();
  const exclusions = "exclusions" in initial ? initial.exclusions : [];
  const [name, setName] = useState(initial.name);
  const [roles, setRoles] = useState(initial.role_keywords ?? []);
  const [locations, setLocations] = useState(initial.location_keywords ?? []);
  const [terms, setTerms] = useState(initial.terms ?? []);
  const [excludedKeywords, setExcludedKeywords] = useState("excluded_keywords" in initial ? initial.excluded_keywords ?? [] : exclusions.filter((item) => item.kind === "keyword").map((item) => item.value));
  const [excludedCompanies, setExcludedCompanies] = useState("excluded_companies" in initial ? initial.excluded_companies ?? [] : exclusions.filter((item) => item.kind === "company").map((item) => item.value));
  const [excludedLocations, setExcludedLocations] = useState("excluded_locations" in initial ? initial.excluded_locations ?? [] : exclusions.filter((item) => item.kind === "location").map((item) => item.value));
  const [workMode, setWorkMode] = useState(initial.work_mode);
  const [remoteOnly, setRemoteOnly] = useState(initial.remote_only ?? false);
  const [radius, setRadius] = useState(initial.radius_km ?? 0);
  const [city, setCity] = useState(() => Object.entries(cities).find(([, coordinates]) => coordinates[0] === initial.center_latitude && coordinates[1] === initial.center_longitude)?.[0] ?? "Toronto");
  const [preview, setPreview] = useState<FilterPreview | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const isExisting = "id" in initial;
  const value: FilterInput = useMemo(() => ({ name: name || "Preview", role_keywords: roles, location_keywords: locations, terms, work_mode: workMode, active: initial.active, remote_only: remoteOnly, radius_km: radius || null, center_latitude: radius ? cities[city][0] : null, center_longitude: radius ? cities[city][1] : null, excluded_keywords: excludedKeywords, excluded_companies: excludedCompanies, excluded_locations: excludedLocations }), [city, excludedCompanies, excludedKeywords, excludedLocations, initial.active, locations, name, radius, remoteOnly, roles, terms, workMode]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!roles.length && !locations.length && !terms.length && !remoteOnly && !radius) setPreview(null);
      else void api.previewFilter(value).then(setPreview).catch(() => setPreview(null));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [api, locations.length, radius, remoteOnly, roles.length, terms.length, value]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setMessage("");
    if (!name.trim()) { setMessage("Give this filter a name."); setPending(false); return; }
    try { const payload = { ...value, name: name.trim(), active: (new FormData(event.currentTarget)).get("active") === "on" }; const saved = isExisting ? await api.updateFilter(initial.id, payload) : await api.createFilter(payload); onSaved(saved); notify(isExisting ? "Filter updated." : "Filter created. Matching has started."); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Could not save filter."); setPending(false); }
  }

  return <section className="editor-panel guided-editor" aria-labelledby="filter-editor-title"><div className="panel-heading"><div><span className="page-eyebrow">{isExisting ? "Edit signal" : "Quick setup"}</span><h2 id="filter-editor-title">{isExisting ? initial.name : "What should we watch for?"}</h2></div><button className="close-button" onClick={onCancel} aria-label="Close filter editor"><X /></button></div><form onSubmit={submit} aria-busy={pending}>
    <div className="field field--wide"><label htmlFor="filter-name"><b>01</b>Name this search</label><input id="filter-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required placeholder="Software internships" /></div>
    <div className="guided-group field--wide"><div className="guided-group__heading"><span>02</span><div><strong>Include</strong><small>Choices within a row broaden the search.</small></div></div><div className="guided-fields"><ChipInput id="roles" label="Roles or fields" values={roles} onChange={setRoles} placeholder="SWE" /><ChipInput id="locations" label="Locations" values={locations} onChange={setLocations} placeholder="Toronto" /><TermPicker values={terms} onChange={setTerms} /></div></div>
    <div className="guided-group field--wide exclusion-group"><div className="guided-group__heading"><span>03</span><div><strong>Exclude</strong><small>Any exclusion blocks a posting before positive scoring.</small></div></div><div className="guided-fields"><ChipInput id="excluded-keywords" label="Keywords" values={excludedKeywords} onChange={setExcludedKeywords} placeholder="unpaid" /><ChipInput id="excluded-companies" label="Companies" values={excludedCompanies} onChange={setExcludedCompanies} placeholder="Example Corp" /><ChipInput id="excluded-locations" label="Locations" values={excludedLocations} onChange={setExcludedLocations} placeholder="United States" /></div></div>
    <div className="field"><label htmlFor="work-mode">Work mode</label><select id="work-mode" value={workMode} onChange={(event) => setWorkMode(event.target.value as WorkMode)}>{["any", "remote", "hybrid", "onsite", "unknown"].map((item) => <option value={item} key={item}>{item}</option>)}</select></div>
    <label className="switch-row"><input type="checkbox" checked={remoteOnly} onChange={(event) => setRemoteOnly(event.target.checked)} /><span><strong>Remote only</strong><small>Exclude hybrid and onsite roles.</small></span></label>
    <div className="radius-controls field--wide"><label>Radius<select value={radius} onChange={(event) => setRadius(Number(event.target.value))}><option value="0">No radius</option><option value="25">25 km</option><option value="50">50 km</option><option value="100">100 km</option><option value="250">250 km</option></select></label>{radius > 0 && <label>From<select value={city} onChange={(event) => setCity(event.target.value)}>{Object.keys(cities).map((item) => <option key={item}>{item}</option>)}</select></label>}</div>
    <label className="switch-row"><input type="checkbox" name="active" defaultChecked={initial.active} /><span><strong>Start watching now</strong><small>Pause any time without deleting it.</small></span></label>
    <Preview value={preview} />{message && <p className="form-message form-message--error" role="alert">{message}</p>}<div className="form-actions"><button type="button" className="button button--ghost" onClick={onCancel}>Cancel</button><button className="button button--primary" disabled={pending}>{pending && <LoaderCircle className="spin" size={18} />}Save and match</button></div>
  </form></section>;
}

function Preview({ value }: { value: FilterPreview | null }) {
  return <div className="filter-live-preview field--wide"><span>Live preview</span>{value ? <><p>{value.estimated_count} current match{value.estimated_count === 1 ? "" : "es"}</p>{Object.entries(value.aliases).map(([alias, meanings]) => <small key={alias}>{alias.toUpperCase()} also matches {meanings.join(", ")}. </small>)}{value.warnings.map((warning) => <strong key={warning}>{warning}</strong>)}<div className="preview-jobs">{value.examples.map((job) => <span key={job.id}>{job.company} · {job.title}</span>)}</div></> : <p>Add criteria to estimate matches.</p>}</div>;
}

function WatchlistPanel({ values, onChange }: { values: CompanyWatchlist[]; onChange: (values: CompanyWatchlist[]) => void }) {
  const { api, notify } = useApp(); const [company, setCompany] = useState("");
  async function add(event: FormEvent) { event.preventDefault(); if (!company.trim()) return; try { const item = await api.createWatchlist({ company: company.trim(), terms: [], locations: [], active: true }); onChange([...values, item]); setCompany(""); notify("Company followed."); } catch (reason) { notify(reason instanceof Error ? reason.message : "Could not follow company.", "error"); } }
  return <section className="watchlist-panel"><div className="panel-heading"><div><span className="page-eyebrow">Company watchlist</span><h2>Never miss a company you care about</h2></div><Building2 /></div><form onSubmit={add}><input aria-label="Company to follow" value={company} onChange={(event) => setCompany(event.target.value)} placeholder="Company name" /><button className="button button--primary">Follow</button></form><div className="watchlist-grid">{values.map((item) => <article className={item.active ? "" : "paused"} key={item.id}><div><strong>{item.company}</strong><small>{item.active ? "Alerts enabled" : "Paused"}</small></div><button onClick={() => void api.updateWatchlist(item.id, { active: !item.active }).then((updated) => onChange(values.map((value) => value.id === item.id ? updated : value)))}>{item.active ? "Pause" : "Resume"}</button><button onClick={() => void api.deleteWatchlist(item.id).then(() => onChange(values.filter((value) => value.id !== item.id)))} aria-label={`Remove ${item.company}`}><Trash2 size={16} /></button></article>)}</div></section>;
}

function TermPicker({ values, onChange }: { values: string[]; onChange: (values: string[]) => void }) { return <div className="field term-field"><span className="field-label">Internship terms</span><div className="term-options" role="group" aria-label="Internship terms">{termOptions.map((term) => <button aria-pressed={values.includes(term)} className={values.includes(term) ? "active" : ""} key={term} onClick={() => onChange(values.includes(term) ? values.filter((value) => value !== term) : [...values, term])} type="button">{term}</button>)}</div></div>; }

function ChipInput({ id, label, values, onChange, placeholder }: { id: string; label: string; values: string[]; onChange: (values: string[]) => void; placeholder: string }) { const [draft, setDraft] = useState(""); function commit() { const value = draft.trim(); if (value && !values.some((item) => item.toLowerCase() === value.toLowerCase()) && values.length < 25) onChange([...values, value]); setDraft(""); } function keyDown(event: KeyboardEvent<HTMLInputElement>) { if (event.key === "Enter" || event.key === ",") { event.preventDefault(); commit(); } else if (event.key === "Backspace" && !draft && values.length) onChange(values.slice(0, -1)); } return <div className="field chip-field"><label htmlFor={id}>{label}</label><div className="chip-input" onClick={(event) => event.currentTarget.querySelector("input")?.focus()}>{values.map((value) => <span key={value}>{value}<button type="button" aria-label={`Remove ${value}`} onClick={() => onChange(values.filter((item) => item !== value))}><X size={13} /></button></span>)}<input id={id} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={keyDown} onBlur={commit} placeholder={values.length ? "Add another" : placeholder} /></div></div>; }
