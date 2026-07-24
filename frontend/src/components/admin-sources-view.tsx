"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Activity, DatabaseZap, Eye, LoaderCircle, Play, Plus, Power, Save, Trash2, X,
} from "lucide-react";

import { useApp } from "./app-provider";
import { PageHeader } from "./dashboard-view";
import { PageError, PageLoading } from "./page-state";
import type {
  AdminSource, AdminSourceInput, AdminSourceRun, SourceAudit, SourcePreview,
} from "@/lib/api/types";

const blank: AdminSourceInput = {
  owner: "", repository: "", branch: "main", path: "README.md", poll_minutes: 60,
  jitter_seconds: 30, default_term: null, parser_schema: "github_markdown_table",
  parser_version: "1",
};

export function AdminSourcesView() {
  const { api } = useApp();
  const [sources, setSources] = useState<AdminSource[]>([]);
  const [audit, setAudit] = useState<SourceAudit[]>([]);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [items, log] = await Promise.all([api.adminSources(), api.sourceAudit()]);
      setSources(items); setAudit(log); setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load source administration.");
    } finally { setLoading(false); }
  }, [api]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (loading) return <PageLoading label="Loading source administration" />;
  if (error) return <PageError message={error} retry={load} />;
  return <div className="app-page admin-source-page">
    <PageHeader eyebrow="Administration" title="Source control room" copy="Validate parser output before a repository can enter the live scheduler." action={<button className="button button--primary" onClick={() => setCreating(true)}><Plus size={17} />Add repository</button>} />
    {creating && <SourceForm initial={blank} cancel={() => setCreating(false)} save={async (value) => { const created = await api.createAdminSource(value); setSources((current) => [...current, created]); setCreating(false); }} />}
    <div className="admin-source-list">{sources.map((source) => <SourceCard key={source.id} value={source} changed={(next) => setSources((current) => current.map((item) => item.id === next.id ? next : item))} removed={() => setSources((current) => current.filter((item) => item.id !== source.id))} />)}</div>
    <section className="admin-audit"><div><Activity /><span><small>Immutable operator trail</small><h2>Recent source changes</h2></span></div>{audit.slice(0, 20).map((event) => <p key={event.id}><strong>{event.action.replaceAll("_", " ")}</strong><span>{new Date(event.created_at).toLocaleString()}</span><code>{event.request_id ?? "no request id"}</code></p>)}</section>
  </div>;
}

function SourceCard({ value, changed, removed }: { value: AdminSource; changed: (value: AdminSource) => void; removed: () => void }) {
  const { api, notify } = useApp();
  const [editing, setEditing] = useState(false);
  const [preview, setPreview] = useState<SourcePreview | null>(null);
  const [runs, setRuns] = useState<AdminSourceRun[]>([]);
  const [pending, setPending] = useState("");
  async function action(name: string, operation: () => Promise<void>) {
    if (pending) return; setPending(name);
    try { await operation(); }
    catch (reason) { notify(reason instanceof Error ? reason.message : `${name} failed.`, "error"); }
    finally { setPending(""); }
  }
  return <article className={`admin-source-card ${value.enabled ? "active" : ""}`}>
    <header><span><DatabaseZap /></span><div><small>{value.owner}</small><h2>{value.repository}</h2><code>{value.path} · {value.branch ?? "default branch"}</code></div><em>{value.enabled ? "Scheduled" : value.last_validated_at ? "Validated" : "Needs preview"}</em></header>
    <dl><div><dt>Cadence</dt><dd>{value.poll_minutes} min + {value.jitter_seconds}s jitter</dd></div><div><dt>Last success</dt><dd>{value.last_succeeded_at ? new Date(value.last_succeeded_at).toLocaleString() : "Never"}</dd></div><div><dt>Failures</dt><dd>{value.consecutive_failures}</dd></div><div><dt>Parser</dt><dd>{value.parser_schema} v{value.parser_version}</dd></div></dl>
    {value.last_error && <p className="source-error">{value.last_error}</p>}
    <div className="admin-source-actions">
      <button onClick={() => setEditing(true)}><Save size={15} />Edit</button>
      <button disabled={Boolean(pending)} onClick={() => void action("Preview", async () => { const result = await api.previewAdminSource(value.id); setPreview(result); changed({ ...value, last_validated_at: result.validation_passed ? new Date().toISOString() : null }); })}><Eye size={15} />Preview</button>
      <button disabled={Boolean(pending) || !value.last_validated_at} onClick={() => void action("Ingestion", async () => { await api.ingestAdminSource(value.id); notify("Ingestion completed."); setRuns(await api.adminSourceRuns(value.id)); })}><Play size={15} />Ingest</button>
      <button disabled={Boolean(pending) || (!value.last_validated_at && !value.enabled)} onClick={() => void action("State change", async () => changed(await api.changeAdminSourceState(value.id, !value.enabled)))}><Power size={15} />{value.enabled ? "Disable" : "Enable"}</button>
      <button onClick={() => void action("History", async () => setRuns(await api.adminSourceRuns(value.id)))}><Activity size={15} />Runs</button>
      <button className="danger" onClick={() => { const confirmation = window.prompt(`Type DELETE ${value.owner}/${value.repository}`); if (confirmation) void action("Deletion", async () => { await api.deleteAdminSource(value.id, confirmation); removed(); }); }}><Trash2 size={15} />Delete</button>
    </div>
    {editing && <SourceForm initial={value} cancel={() => setEditing(false)} save={async (input) => { changed(await api.updateAdminSource(value.id, input)); setEditing(false); }} />}
    {preview && <PreviewPanel value={preview} close={() => setPreview(null)} />}
    {runs.length > 0 && <div className="source-runs"><h3>Recent runs</h3>{runs.slice(0, 10).map((run) => <p key={run.id}><strong>{run.status}</strong><span>{run.accepted_count} accepted · {run.rejected_count} rejected · {run.duplicate_count} duplicates</span><small>{new Date(run.started_at).toLocaleString()}</small></p>)}</div>}
  </article>;
}

function SourceForm({ initial, cancel, save }: { initial: AdminSourceInput | AdminSource; cancel: () => void; save: (value: AdminSourceInput) => Promise<void> }) {
  const { notify } = useApp(); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); const data = new FormData(event.currentTarget);
    try { await save({ owner:String(data.get("owner")),repository:String(data.get("repository")),branch:String(data.get("branch"))||null,path:String(data.get("path")),poll_minutes:Number(data.get("poll")),jitter_seconds:Number(data.get("jitter")),default_term:String(data.get("term"))||null,parser_schema:"github_markdown_table",parser_version:"1" }); notify("Source configuration saved."); }
    catch (reason) { notify(reason instanceof Error ? reason.message : "Could not save source.", "error"); setPending(false); }
  }
  return <form className="source-editor" onSubmit={submit}><button className="close-button" type="button" onClick={cancel}><X /></button><label>Owner<input name="owner" defaultValue={initial.owner} required /></label><label>Repository<input name="repository" defaultValue={initial.repository} required /></label><label>Branch<input name="branch" defaultValue={initial.branch ?? ""} /></label><label>Path<input name="path" defaultValue={initial.path} required /></label><label>Poll minutes<input name="poll" type="number" min="5" max="1440" defaultValue={initial.poll_minutes} /></label><label>Jitter seconds<input name="jitter" type="number" min="0" max="300" defaultValue={initial.jitter_seconds} /></label><label>Default term<input name="term" defaultValue={initial.default_term ?? ""} placeholder="Optional" /></label><label>Parser schema<input value={initial.parser_schema} readOnly /></label><label>Parser version<input value={initial.parser_version} readOnly /></label><button className="button button--primary" disabled={pending}>{pending && <LoaderCircle className="spin" />}Save disabled source</button></form>;
}

function PreviewPanel({ value, close }: { value: SourcePreview; close: () => void }) {
  return <section className="source-preview"><header><div><small>Read-only parser preview</small><h3>{value.accepted} accepted from {value.rows_fetched} fetched</h3></div><button onClick={close}><X /></button></header>{!value.validation_passed && <div className="notice error"><strong>Source cannot be enabled yet.</strong>{value.validation_errors.map((error) => <span key={error}>{error}</span>)}</div>}<div className="preview-metrics"><span>{value.rejected}<small>Rejected</small></span><span>{value.duplicate_candidates}<small>Known rows</small></span><span>{value.application_domains.length}<small>Domains</small></span></div><p>Detected schema: {value.detected_table_schema}</p><p>Terms: {value.inferred_terms.map((item) => `${item.term} (${item.count})`).join(", ") || "Unknown"}</p>{value.missing_columns.length > 0 && <strong>Missing: {value.missing_columns.join(", ")}</strong>}{value.suspicious_truncated_values.map((item) => <strong key={item}>Review title: {item}</strong>)}<div className="preview-table">{value.sample_normalized_output.map((item) => <p key={item.canonical_fingerprint}><b>{item.company}</b><span>{item.title}</span><small>{item.location ?? "Unknown location"} · {item.term ?? "Unknown term"}</small><a href={item.application_url} target="_blank" rel="noreferrer">{item.application_domain}</a></p>)}</div>{value.rejected_rows.length > 0 && <details><summary>Rejected rows</summary>{value.rejected_rows.map((row) => <code key={row}>{row}</code>)}</details>}</section>;
}
