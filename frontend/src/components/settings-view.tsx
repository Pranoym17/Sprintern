"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Check, Download, Link2, LoaderCircle, Mail, RefreshCw, Send, ShieldCheck, Trash2, Unlink,
} from "lucide-react";

import { useApp } from "./app-provider";
import { PageHeader } from "./dashboard-view";
import { PageError, PageLoading } from "./page-state";
import type { DeliveryChannel, DeliveryQueue, Profile } from "@/lib/api/types";

const consentTypes = [
  "new_match", "deadline", "saved", "follow_up", "interview", "posting_updated",
  "posting_reopened", "weekly_progress",
];
const administratorConsentTypes = ["source_stale", "parser_broken"];
const consentLabels: Record<string, string> = {
  new_match: "New matches",
  deadline: "Deadline reminders",
  saved: "Saved-job reminders",
  follow_up: "Follow-up reminders",
  interview: "Interview reminders",
  posting_updated: "Posting updates",
  posting_reopened: "Reopened postings",
  weekly_progress: "Weekly application progress",
  source_stale: "Job data is delayed",
  parser_broken: "Job import needs attention",
};

export function SettingsView() {
  const { api, notify, signOut } = useApp();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [queue, setQueue] = useState<DeliveryQueue | null>(null);
  const [pending, setPending] = useState(false);
  const [channelPending, setChannelPending] = useState(false);
  const [error, setError] = useState("");
  const [link, setLink] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [accountPending, setAccountPending] = useState(false);
  const [administrator, setAdministrator] = useState(false);

  const load = useCallback(async () => {
    try {
      const [next, deliveryQueue, admin] = await Promise.all([
        api.profile(), api.notificationQueue(), api.adminAccess().then(() => true).catch(() => false),
      ]);
      setProfile(next); setQueue(deliveryQueue); setAdministrator(admin); setError(""); return next;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load settings.");
      return null;
    }
  }, [api]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      const next = await api.updateProfile({
        timezone: String(data.get("timezone")),
        email_notifications_enabled: data.get("email") === "on",
        preferred_email_time: String(data.get("email_time")),
        email_digest_job_limit: Number(data.get("digest_limit")),
        email_empty_digest_enabled: data.get("empty_digest") === "on",
        telegram_notifications_enabled:
          profile.telegram_chat_id !== null && data.get("telegram") === "on",
        quiet_hours_start: String(data.get("quiet_start") || "") || null,
        quiet_hours_end: String(data.get("quiet_end") || "") || null,
        weekend_pause: data.get("weekend_pause") === "on",
        max_alerts_per_day: Number(data.get("max_alerts")),
        notification_consents: {
          ...profile.notification_consents,
          ...Object.fromEntries(
            [...consentTypes, ...(administrator ? administratorConsentTypes : [])]
              .map((kind) => [kind, data.get(`consent_${kind}`) === "on"]),
          ),
        },
      });
      setProfile(next);
      notify("Notification preferences saved.");
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Save failed.", "error");
    } finally { setPending(false); }
  }

  async function connect() {
    if (channelPending) return;
    setChannelPending(true);
    try {
      const result = await api.createTelegramLink();
      setLink(result.deep_link);
      window.open(result.deep_link, "_blank", "noopener,noreferrer");
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Could not create link.", "error");
    } finally { setChannelPending(false); }
  }

  async function refresh() {
    if (channelPending) return;
    setChannelPending(true);
    const next = await load();
    notify(
      next?.telegram_chat_id
        ? "Telegram connected. You can enable alerts now."
        : "Telegram is not linked yet. Press Start in the bot, then try again.",
      next?.telegram_chat_id ? "success" : "error",
    );
    setChannelPending(false);
  }

  async function disconnect() {
    if (channelPending || !window.confirm("Disconnect Telegram from Sprintern?")) return;
    setChannelPending(true);
    try {
      await api.unlinkTelegram();
      setProfile((current) => current
        ? { ...current, telegram_chat_id: null, telegram_notifications_enabled: false }
        : current);
      setLink(""); notify("Telegram disconnected.");
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Disconnect failed.", "error");
    } finally { setChannelPending(false); }
  }

  async function sendTest(channel: DeliveryChannel) {
    try {
      const result = await api.testNotification(channel);
      notify(
        result.outcome === "sent"
          ? `${channel === "email" ? "Email" : "Telegram"} test sent.`
          : result.error ?? "Provider rejected the test.",
        result.outcome === "sent" ? "success" : "error",
      );
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Test failed.", "error");
    }
  }

  async function exportAccount() {
    if (accountPending) return;
    setAccountPending(true);
    try {
      const data = await api.exportAccount();
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `sprintern-export-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click(); URL.revokeObjectURL(url); notify("Your data export is ready.");
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : "Export failed.", "error");
    } finally { setAccountPending(false); }
  }

  async function deleteAccount() {
    if (accountPending || deleteConfirmation !== "DELETE") return;
    setAccountPending(true);
    try { await api.deleteAccount(); await signOut(); }
    catch (reason) {
      notify(reason instanceof Error ? reason.message : "Account deletion failed.", "error");
      setAccountPending(false);
    }
  }

  if (!profile && !error) return <PageLoading label="Loading settings" />;
  if (error || !profile) return <PageError message={error || "Profile unavailable."} retry={load} />;

  return <div className="app-page notification-page">
    <PageHeader
      eyebrow="Notifications"
      title="Be first without staying online"
      copy="Choose where alerts land, how quickly they arrive, and when Sprintern should wait."
    />
    <form onSubmit={save} aria-busy={pending}>
      <section className="preference-section">
        <PreferenceHeading number="01" title="Choose your channels" copy="Each channel stays off until you explicitly enable it." />
        <div className="channel-grid">
          <label className={`channel-card ${profile.telegram_chat_id ? "channel-card--connected" : ""}`}>
            <span className="channel-icon channel-icon--telegram"><Send /></span>
            <span className="channel-copy"><strong>Telegram</strong><small>{profile.telegram_chat_id ? "Connected and ready" : "Not connected — link the bot"}</small>{profile.telegram_chat_id && <em><Check size={13} />Connected</em>}</span>
            {profile.telegram_chat_id && <input type="checkbox" name="telegram" defaultChecked={profile.telegram_notifications_enabled} aria-label="Enable Telegram alerts" />}
          </label>
          <label className={`channel-card ${profile.email_notifications_enabled ? "channel-card--connected" : ""}`}>
            <span className="channel-icon"><Mail /></span>
            <span className="channel-copy"><strong>Email</strong><small>{profile.email ?? "No email on account"}</small><em>{profile.email_notifications_enabled ? <><Check size={13} />Connected and active</> : "Connected — alerts off"}</em></span>
            <input type="checkbox" name="email" disabled={!profile.email || Boolean(profile.email_suppressed_at)} defaultChecked={profile.email_notifications_enabled} aria-label="Enable email alerts" />
          </label>
        </div>
        <div className="telegram-actions">
          {profile.telegram_chat_id
            ? <button className="icon-text-button" type="button" onClick={disconnect}><Unlink size={16} />Disconnect Telegram</button>
            : <><button className="button button--dark button--small" type="button" onClick={connect}><Link2 size={16} />Open Telegram bot</button>{link && <button className="button button--ghost button--small" type="button" onClick={refresh}><RefreshCw size={16} />Check status</button>}</>}
          <button className="button button--ghost button--small" type="button" disabled={!profile.telegram_notifications_enabled} onClick={() => void sendTest("telegram")}>Test Telegram</button>
          <button className="button button--ghost button--small" type="button" disabled={!profile.email_notifications_enabled} onClick={() => void sendTest("email")}>Test email</button>
        </div>
      </section>

      <section className="preference-section">
        <PreferenceHeading number="02" title="Shape your daily email" copy="Telegram sends every new match immediately. Email sends one ranked highlights digest at your chosen local time." />
        <div className="notification-guardrails">
          <label>Daily delivery time<input name="email_time" type="time" required defaultValue={profile.preferred_email_time.slice(0, 5)} /></label>
          <label>Top matches per email<input name="digest_limit" type="number" min="1" max="10" required defaultValue={profile.email_digest_job_limit} /></label>
        </div>
        <label className="switch-row"><input type="checkbox" name="empty_digest" defaultChecked={profile.email_empty_digest_enabled} /><span><strong>Email me when there are no matches</strong><small>Off by default. When off, Sprintern skips empty days.</small></span></label>
      </section>

      <section className="preference-section preference-section--compact">
        <PreferenceHeading number="03" title="Local-time guardrails" copy="Your email time follows this timezone and handles daylight-saving changes automatically. Instant Telegram matches are never delayed." />
        <div className="field timezone-field"><label htmlFor="timezone">Timezone</label><input id="timezone" name="timezone" defaultValue={profile.timezone} required /><span className="field__help">IANA format, for example America/Toronto.</span></div>
        <div className="notification-guardrails">
          <label>Quiet from<input name="quiet_start" type="time" defaultValue={profile.quiet_hours_start?.slice(0, 5) ?? ""} /></label>
          <label>Until<input name="quiet_end" type="time" defaultValue={profile.quiet_hours_end?.slice(0, 5) ?? ""} /></label>
          <label>Daily maximum<input name="max_alerts" type="number" min="1" max="500" defaultValue={profile.max_alerts_per_day} /></label>
        </div>
        <label className="switch-row"><input type="checkbox" name="weekend_pause" defaultChecked={profile.weekend_pause} /><span><strong>Pause on weekends</strong><small>Queued alerts resume Monday morning.</small></span></label>
      </section>

      <section className="preference-section">
        <PreferenceHeading number="04" title="Notification types" copy="Control lifecycle reminders separately from new-match alerts." />
        <div className="consent-grid">{[...consentTypes, ...(administrator ? administratorConsentTypes : [])].map((kind) => <label className="switch-row" key={kind}><input type="checkbox" name={`consent_${kind}`} defaultChecked={profile.notification_consents[kind] !== false} /><span><strong>{consentLabels[kind]}</strong></span></label>)}</div>
        {queue && <p className="delivery-queue-status">{queue.pending} queued · {queue.delayed_by_quiet_hours + queue.delayed_by_weekend + queue.delayed_by_daily_cap} delayed by guardrails · {queue.failed} retrying · {queue.suppressed} suppressed</p>}
      </section>
      <div className="settings-save"><p>Changes affect future delivery attempts.</p><button className="button button--primary" disabled={pending}>{pending && <LoaderCircle className="spin" size={18} />}Save preferences</button></div>
    </form>

    {administrator && <section className="account-controls"><div><span className="page-eyebrow">Administrator</span><h2>Source control room</h2><p>Add, validate, schedule and monitor repository parsers without exposing the internal API key.</p></div><Link className="button button--dark button--small" href="/admin/sources"><ShieldCheck size={17} />Manage sources</Link></section>}

    <section className="account-controls" aria-labelledby="account-controls-title">
      <div><span className="page-eyebrow">Account controls</span><h2 id="account-controls-title">Your data, your choice</h2><p>Download your data or permanently remove your account.</p></div>
      <button className="button button--ghost button--small" type="button" disabled={accountPending} onClick={exportAccount}><Download size={17} />Export my data</button>
      <div className="danger-zone"><div><h3>Delete account</h3><p>This permanently removes your profile, filters, matches, delivery history, and sign-in account.</p></div><div className="field"><label htmlFor="delete-confirmation">Type DELETE to confirm</label><input id="delete-confirmation" autoComplete="off" value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} /></div><button className="button button--danger button--small" type="button" disabled={accountPending || deleteConfirmation !== "DELETE"} onClick={deleteAccount}><Trash2 size={17} />Delete account</button></div>
    </section>
  </div>;
}

function PreferenceHeading({ number, title, copy }: { number: string; title: string; copy: string }) {
  return <div className="preference-heading"><span>{number}</span><div><h2>{title}</h2><p>{copy}</p></div></div>;
}
