"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, ChevronDown, Download, FileUp, Target, Trash2, X } from "lucide-react";

import { useApp } from "./app-provider";
import { EmptyState, PageHeader } from "./dashboard-view";
import { PageError, PageLoading } from "./page-state";
import type {
  Application, ApplicationStage, CSVImportResult, WeeklyProgress,
} from "@/lib/api/types";

const stages: ApplicationStage[] = ["saved", "preparing", "applied", "oa", "interview", "offer", "rejected", "withdrawn"];
const importFields = ["company", "title", "location", "stage", "applied_at", "notes", "application_url"];

export function ApplicationsView() {
  const { api, notify } = useApp();
  const [items, setItems] = useState<Application[]>([]);
  const [goal, setGoal] = useState<WeeklyProgress | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showImport, setShowImport] = useState(false);

  const load = useCallback(async () => {
    try { const [applications, progress] = await Promise.all([api.applications(), api.weeklyGoal()]); setItems(applications); setGoal(progress); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load your tracker."); }
    finally { setLoading(false); }
  }, [api]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  async function update(item: Application, values: Record<string, unknown>) {
    try { const changed = await api.updateApplication(item.id, values); setItems((current) => current.map((value) => value.id === item.id ? changed : value)); notify("Application updated."); }
    catch (reason) { notify(reason instanceof Error ? reason.message : "Update failed.", "error"); }
  }

  if (loading) return <PageLoading label="Loading application tracker" />;
  if (error) return <PageError message={error} retry={load} />;

  return <div className="app-page tracker-page">
    <PageHeader eyebrow="Application tracker" title="Turn searching into progress" copy="Keep the current stage simple while preserving every change in the timeline." action={<button className="button button--ghost" onClick={() => setShowImport((value) => !value)}><FileUp size={17} />Import CSV</button>} />
    {goal && <GoalCard value={goal} save={async (value) => { const updated = await api.updateWeeklyGoal(value); setGoal(updated); notify("Weekly goal updated."); }} />}
    {showImport && <ImportPanel close={() => setShowImport(false)} complete={() => { setShowImport(false); void load(); }} />}
    <div className="tracker-toolbar"><strong>{items.length} tracked application{items.length === 1 ? "" : "s"}</strong><div><button onClick={() => void api.download("/exports/applications.csv", "sprintern-applications.csv")}><Download size={15} />Applications CSV</button><button onClick={() => void api.download("/exports/timeline.csv", "sprintern-timeline.csv")}><Download size={15} />Timeline CSV</button><button onClick={() => downloadApplicationsJson(items)}><Download size={15} />Tracker JSON</button></div></div>
    {items.length ? <div className="application-list">{items.map((item) => <article key={item.id} className={`application-card stage-${item.stage}`}><div className="application-summary"><span className="company-avatar">{item.job.company.slice(0, 2).toUpperCase()}</span><div><small>{item.job.company}</small><h2>{item.job.title}</h2><span>{item.job.location ?? "Location not listed"}</span></div><select aria-label={`Stage for ${item.job.title}`} value={item.stage} onChange={(event) => void update(item, { stage: event.target.value })}>{stages.map((stage) => <option key={stage} value={stage}>{stageLabel(stage)}</option>)}</select><button aria-label={`Details for ${item.job.title}`} onClick={() => setExpanded(expanded === item.id ? null : item.id)}><ChevronDown className={expanded === item.id ? "open" : ""} /></button></div>{expanded === item.id && <ApplicationDetails item={item} update={(values) => update(item, values)} remove={async () => { if (!window.confirm("Remove this application and its timeline?")) return; await api.deleteApplication(item.id); setItems((current) => current.filter((value) => value.id !== item.id)); }} />}</article>)}</div> : <EmptyState icon={<CalendarClock />} title="Your tracker is ready" copy="Save a match or mark it applied and it will appear here automatically." action="/matches" actionLabel="Browse matches" />}
  </div>;
}

function ApplicationDetails({ item, update, remove }: { item: Application; update: (values: Record<string, unknown>) => Promise<void>; remove: () => Promise<void> }) {
  const [notes, setNotes] = useState(item.notes ?? "");
  return <div className="application-details"><div className="application-fields"><label>Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} onBlur={() => { if (notes !== (item.notes ?? "")) void update({ notes }); }} placeholder="Interview prep, requirements, people to contact…" /></label><DateField label="Application deadline" value={item.deadline_at} change={(value) => update({ deadline_at: value })} /><DateField label="Follow-up" value={item.follow_up_at} change={(value) => update({ follow_up_at: value })} /><DateField label="Interview" value={item.interview_at} change={(value) => update({ interview_at: value })} /><TextField label="Recruiter/contact" value={item.contact} change={(value) => update({ contact: value })} /><TextField label="Resume version" value={item.resume_version} change={(value) => update({ resume_version: value })} /><TextField label="Application URL" value={item.application_url} change={(value) => update({ application_url: value })} /><TextField label="Outcome" value={item.outcome} change={(value) => update({ outcome: value })} /></div><div className="application-timeline"><h3>History</h3>{[...item.events].reverse().map((event) => <div key={event.id}><i /><span><strong>{event.event_type.replaceAll("_", " ")}</strong><small>{new Date(event.created_at).toLocaleString()}</small></span></div>)}</div><button className="tracker-delete" onClick={() => void remove()}><Trash2 size={15} />Remove from tracker</button></div>;
}

function DateField({ label, value, change }: { label: string; value: string | null; change: (value: string | null) => Promise<void> }) { return <label>{label}<input type="datetime-local" defaultValue={value ? new Date(value).toISOString().slice(0, 16) : ""} onBlur={(event) => void change(event.target.value ? new Date(event.target.value).toISOString() : null)} /></label>; }
function TextField({ label, value, change }: { label: string; value: string | null; change: (value: string | null) => Promise<void> }) { return <label>{label}<input defaultValue={value ?? ""} onBlur={(event) => { const next = event.target.value.trim() || null; if (next !== value) void change(next); }} /></label>; }

function GoalCard({ value, save }: { value: WeeklyProgress; save: (value: { target: number; reminders_enabled: boolean; streaks_enabled: boolean }) => Promise<void> }) {
  const [target, setTarget] = useState(value.target);
  const percent = target ? Math.min(100, Math.round(value.applied / target * 100)) : 100;
  return <section className="goal-card"><span><Target /></span><div><small>This week</small><strong>{value.applied} of {target} applications</strong><div><i style={{ width: `${percent}%` }} /></div></div><label>Weekly goal<input type="number" min="0" max="100" value={target} onChange={(event) => setTarget(Number(event.target.value))} onBlur={() => void save({ target, reminders_enabled: value.reminders_enabled, streaks_enabled: value.streaks_enabled })} /></label><p>{value.interviews} interviews · {value.offers} offers{value.streaks_enabled ? ` · ${value.current_streak} week streak` : ""}</p></section>;
}

function ImportPanel({ close, complete }: { close: () => void; complete: () => void }) {
  const { api, notify } = useApp(); const [csvText, setCsvText] = useState(""); const [mapping, setMapping] = useState<Record<string, string>>({}); const [result, setResult] = useState<CSVImportResult | null>(null);
  const columns = useMemo(() => csvText.split(/\r?\n/, 1)[0]?.split(",").map((value) => value.trim().replaceAll('"', "")) ?? [], [csvText]);
  useEffect(() => { const timer = window.setTimeout(() => setMapping(Object.fromEntries(importFields.filter((field) => columns.includes(field)).map((field) => [field, field]))), 0); return () => window.clearTimeout(timer); }, [columns]);
  async function run(dryRun: boolean) { try { const response = await api.importApplications(csvText, mapping, dryRun); setResult(response); if (!dryRun) { notify(`${response.imported_rows} applications imported.`); complete(); } } catch (reason) { notify(reason instanceof Error ? reason.message : "Import failed.", "error"); } }
  return <section className="import-panel"><div className="panel-heading"><div><span className="page-eyebrow">CSV import</span><h2>Preview before writing anything</h2></div><button onClick={close}><X /></button></div><textarea aria-label="CSV data" value={csvText} onChange={(event) => setCsvText(event.target.value)} placeholder={'company,title,stage,notes\nAcme,Software Intern,applied,Follow up Friday'} /><div className="mapping-grid">{importFields.slice(0, 5).map((field) => <label key={field}>{field}<select value={mapping[field] ?? ""} onChange={(event) => setMapping((current) => ({ ...current, [field]: event.target.value }))}><option value="">Not mapped</option>{columns.map((column) => <option key={column}>{column}</option>)}</select></label>)}</div>{result && <p>{result.valid_rows} valid · {result.duplicate_rows} duplicates · {result.errors.length} errors</p>}<div className="form-actions"><button className="button button--ghost" onClick={() => void run(true)}>Dry run</button><button className="button button--primary" disabled={!result || !!result.errors.length} onClick={() => void run(false)}>Import valid rows</button></div></section>;
}

function stageLabel(stage: ApplicationStage) { return stage === "oa" ? "Online assessment" : stage[0].toUpperCase() + stage.slice(1); }

export function downloadApplicationsJson(items: Application[]) {
  const url = URL.createObjectURL(new Blob(
    [JSON.stringify({ exported_at: new Date().toISOString(), applications: items }, null, 2)],
    { type: "application/json" },
  ));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `sprintern-tracker-${new Date().toISOString().slice(0, 10)}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}
