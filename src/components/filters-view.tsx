"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useState } from "react";
import { Filter as FilterIcon, LoaderCircle, Pencil, Plus, Power, Trash2, X } from "lucide-react";

import { useApp } from "./app-provider";
import { EmptyState, PageHeader } from "./dashboard-view";
import { PageError, PageLoading } from "./page-state";
import type { FilterInput, JobFilter, WorkMode } from "@/lib/api/types";

const blank: FilterInput = { name: "", role_keywords: [], location_keywords: [], terms: ["Summer 2027"], work_mode: "any", active: true };

export function FiltersView() {
  const { api, notify } = useApp();
  const [filters, setFilters] = useState<JobFilter[]>([]);
  const [editing, setEditing] = useState<JobFilter | "new" | null>(null);
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setFilters(await api.filters()); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load filters."); }
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
    catch (reason) { notify(reason instanceof Error ? reason.message : "Delete failed.", "error"); setPendingIds((current) => { const next = new Set(current); next.delete(filter.id); return next; }); }
  }

  if (loading) return <PageLoading label="Loading filters" />;
  if (error) return <PageError message={error} retry={load} />;

  return <div className="app-page">
    <PageHeader eyebrow="Filters" title="Tune your signal" copy="A few specific choices are enough. Sprintern handles the repeated searching." action={<button className="button button--primary" onClick={() => setEditing("new")}><Plus size={18} />New filter</button>} />
    {editing && <FilterEditor initial={editing === "new" ? blank : editing} onCancel={() => setEditing(null)} onSaved={(value) => { setFilters((current) => editing === "new" ? [value, ...current] : current.map((item) => item.id === value.id ? value : item)); setEditing(null); }} />}
    {filters.length ? <div className="filter-list">{filters.map((filter) => <article className={`filter-card ${filter.active ? "filter-card--active" : "filter-card--paused"}`} key={filter.id}>
      <div className="filter-card__heading"><span className="feature-icon"><FilterIcon size={20} /></span><div><h2>{filter.name}</h2><span className={`status-pill ${filter.active ? "status-pill--matched" : ""}`}>{filter.active ? "Actively watching" : "Paused"}</span></div><div className="filter-card__controls"><button disabled={pendingIds.has(filter.id)} onClick={() => setEditing(filter)} aria-label={`Edit ${filter.name}`}><Pencil size={18} /></button><button disabled={pendingIds.has(filter.id)} onClick={() => toggle(filter)} aria-label={`${filter.active ? "Pause" : "Activate"} ${filter.name}`}><Power size={18} /></button><button disabled={pendingIds.has(filter.id)} className="danger" onClick={() => remove(filter)} aria-label={`Delete ${filter.name}`}><Trash2 size={18} /></button></div></div>
      <dl className="filter-details"><div><dt>Roles</dt><dd>{filter.role_keywords.length ? filter.role_keywords.join(", ") : "Any role"}</dd></div><div><dt>Locations</dt><dd>{filter.location_keywords.length ? filter.location_keywords.join(", ") : "Any location"}</dd></div><div><dt>Term</dt><dd>{filter.terms.length ? filter.terms.join(", ") : "Any term"}</dd></div><div><dt>Work mode</dt><dd>{filter.work_mode}</dd></div></dl>
    </article>)}</div> : !editing && <EmptyState icon={<FilterIcon />} title="Create your first signal" copy="Add the roles, places, and internship term you care about. Sprintern will take it from there." />}
  </div>;
}

function FilterEditor({ initial, onCancel, onSaved }: { initial: FilterInput | JobFilter; onCancel: () => void; onSaved: (value: JobFilter) => void }) {
  const { api, notify } = useApp();
  const [roles, setRoles] = useState(initial.role_keywords);
  const [locations, setLocations] = useState(initial.location_keywords);
  const [terms, setTerms] = useState(initial.terms);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const isExisting = "id" in initial;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setMessage("");
    const data = new FormData(event.currentTarget);
    const value: FilterInput = { name: String(data.get("name") ?? "").trim(), role_keywords: roles, location_keywords: locations, terms, work_mode: String(data.get("work_mode")) as WorkMode, active: data.get("active") === "on" };
    if (!roles.length && !locations.length && !terms.length && value.work_mode === "any") { setMessage("Add at least one criterion so the filter is useful."); setPending(false); return; }
    try { const saved = isExisting ? await api.updateFilter(initial.id, value) : await api.createFilter(value); onSaved(saved); notify(isExisting ? "Filter updated." : "Filter created. Matching has started."); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Could not save filter."); setPending(false); }
  }

  return <section className="editor-panel guided-editor" aria-labelledby="filter-editor-title">
    <div className="panel-heading"><div><span className="page-eyebrow">{isExisting ? "Edit signal" : "Quick setup"}</span><h2 id="filter-editor-title">{isExisting ? initial.name : "What should we watch for?"}</h2></div><button className="close-button" onClick={onCancel} aria-label="Close filter editor"><X /></button></div>
    <form onSubmit={submit} aria-busy={pending}>
      <div className="field field--wide"><label htmlFor="filter-name"><b>01</b>Name this search</label><input id="filter-name" name="name" defaultValue={initial.name} maxLength={100} required placeholder="Software internships" /></div>
      <div className="guided-group field--wide"><div className="guided-group__heading"><span>02</span><div><strong>Add what matters</strong><small>Press Enter after each keyword. Choices within a row broaden the search.</small></div></div><div className="guided-fields"><ChipInput id="roles" label="Roles or fields" values={roles} onChange={setRoles} placeholder="software" /><ChipInput id="locations" label="Locations" values={locations} onChange={setLocations} placeholder="Toronto" /><ChipInput id="terms" label="Internship term" values={terms} onChange={setTerms} placeholder="Summer 2027" /></div></div>
      <div className="field"><label htmlFor="work-mode"><b>03</b>Work mode</label><select id="work-mode" name="work_mode" defaultValue={initial.work_mode}>{["any", "remote", "hybrid", "onsite", "unknown"].map((value) => <option value={value} key={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></div>
      <label className="switch-row"><input type="checkbox" name="active" defaultChecked={initial.active} /><span><strong>Start watching now</strong><small>Pause this filter any time without deleting it.</small></span></label>
      <div className="filter-live-preview field--wide"><span>Signal preview</span><p>{previewSentence(roles, locations, terms)}</p><small>Exact match counts appear after saving because matching runs on the server.</small></div>
      {message && <p className="form-message form-message--error" role="alert">{message}</p>}
      <div className="form-actions"><button type="button" className="button button--ghost" onClick={onCancel}>Cancel</button><button className="button button--primary" disabled={pending}>{pending && <LoaderCircle className="spin" size={18} />}Save and match</button></div>
    </form>
  </section>;
}

function ChipInput({ id, label, values, onChange, placeholder }: { id: string; label: string; values: string[]; onChange: (values: string[]) => void; placeholder: string }) {
  const [draft, setDraft] = useState("");
  function commit() { const value = draft.trim(); if (value && !values.some((item) => item.toLowerCase() === value.toLowerCase()) && values.length < 25) onChange([...values, value]); setDraft(""); }
  function keyDown(event: KeyboardEvent<HTMLInputElement>) { if (event.key === "Enter" || event.key === ",") { event.preventDefault(); commit(); } else if (event.key === "Backspace" && !draft && values.length) onChange(values.slice(0, -1)); }
  return <div className="field chip-field"><label htmlFor={id}>{label}</label><div className="chip-input" onClick={(event) => event.currentTarget.querySelector("input")?.focus()}>{values.map((value) => <span key={value}>{value}<button type="button" aria-label={`Remove ${value}`} onClick={() => onChange(values.filter((item) => item !== value))}><X size={13} /></button></span>)}<input id={id} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={keyDown} onBlur={commit} placeholder={values.length ? "Add another" : placeholder} /></div></div>;
}

function previewSentence(roles: string[], locations: string[], terms: string[]) {
  return `Watch for ${roles.length ? roles.join(" or ") : "any internship role"}${locations.length ? ` in ${locations.join(" or ")}` : " anywhere"}${terms.length ? ` for ${terms.join(" or ")}` : " in any term"}.`;
}
