"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Check, Link2, LoaderCircle, Mail, RefreshCw, Send, Unlink } from "lucide-react";

import { useApp } from "./app-provider";
import { PageHeader } from "./dashboard-view";
import { PageError, PageLoading } from "./page-state";
import type { NotificationCadence, Profile } from "@/lib/api/types";

export function SettingsView() {
  const { api, notify } = useApp();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [pending, setPending] = useState(false);
  const [channelPending, setChannelPending] = useState(false);
  const [error, setError] = useState("");
  const [link, setLink] = useState("");

  const load = useCallback(async () => {
    try { const next = await api.profile(); setProfile(next); setError(""); return next; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load settings."); return null; }
  }, [api]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!profile) return; setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      setProfile(await api.updateProfile({ timezone: String(data.get("timezone")), notification_cadence: String(data.get("cadence")) as NotificationCadence, email_notifications_enabled: data.get("email") === "on", telegram_notifications_enabled: profile.telegram_chat_id !== null && data.get("telegram") === "on" }));
      notify("Notification preferences saved.");
    } catch (reason) { notify(reason instanceof Error ? reason.message : "Save failed.", "error"); }
    finally { setPending(false); }
  }

  async function connect() {
    if (channelPending) return; setChannelPending(true);
    try { const result = await api.createTelegramLink(); setLink(result.deep_link); window.open(result.deep_link, "_blank", "noopener,noreferrer"); }
    catch (reason) { notify(reason instanceof Error ? reason.message : "Could not create link.", "error"); }
    finally { setChannelPending(false); }
  }

  async function refresh() {
    if (channelPending) return; setChannelPending(true);
    const next = await load();
    if (next?.telegram_chat_id) notify("Telegram connected. You can enable alerts now.");
    else notify("Telegram is not linked yet. Press Start in the bot, then try again.", "error");
    setChannelPending(false);
  }

  async function disconnect() {
    if (channelPending || !window.confirm("Disconnect Telegram from Sprintern?")) return; setChannelPending(true);
    try { await api.unlinkTelegram(); setProfile((current) => current ? { ...current, telegram_chat_id: null, telegram_notifications_enabled: false } : current); setLink(""); notify("Telegram disconnected."); }
    catch (reason) { notify(reason instanceof Error ? reason.message : "Disconnect failed.", "error"); }
    finally { setChannelPending(false); }
  }

  if (!profile && !error) return <PageLoading label="Loading settings" />;
  if (error || !profile) return <PageError message={error || "Profile unavailable."} retry={load} />;

  return <div className="app-page notification-page">
    <PageHeader eyebrow="Notifications" title="Be first without staying online" copy="Choose where alerts land and how quickly they arrive." />
    <form onSubmit={save} aria-busy={pending}>
      <section className="preference-section"><div className="preference-heading"><span>01</span><div><h2>Choose your channels</h2><p>Telegram is ready now. Email begins once the project sender is configured.</p></div></div><div className="channel-grid">
        <label className={`channel-card ${profile.telegram_chat_id ? "channel-card--connected" : ""}`}><span className="channel-icon channel-icon--telegram"><Send /></span><span className="channel-copy"><strong>Telegram</strong><small>{profile.telegram_chat_id ? "Connected and ready" : "Not connected — link the bot"}</small>{profile.telegram_chat_id && <em><Check size={13} />Connected</em>}</span>{profile.telegram_chat_id && <input type="checkbox" name="telegram" defaultChecked={profile.telegram_notifications_enabled} aria-label="Enable Telegram alerts" />}</label>
        <label className="channel-card"><span className="channel-icon"><Mail /></span><span className="channel-copy"><strong>Email</strong><small>{profile.email ?? "No email on account"}</small><em className="channel-note">Sender setup pending</em></span><input type="checkbox" name="email" defaultChecked={profile.email_notifications_enabled} aria-label="Enable email alerts" /></label>
      </div>
      <div className="telegram-actions">{profile.telegram_chat_id ? <button className="icon-text-button" type="button" disabled={channelPending} onClick={disconnect}><Unlink size={16} />Disconnect Telegram</button> : <><button className="button button--dark button--small" type="button" disabled={channelPending} onClick={connect}><Link2 size={16} />Open Telegram bot</button>{link && <button className="button button--ghost button--small" type="button" disabled={channelPending} onClick={refresh}><RefreshCw size={16} />I pressed Start — check status</button>}</>}</div></section>

      <section className="preference-section"><div className="preference-heading"><span>02</span><div><h2>Set the pace</h2><p>Instant is recommended while application windows move quickly.</p></div></div><div className="cadence-control" role="group" aria-label="Notification cadence">{(["instant", "hourly", "daily"] as NotificationCadence[]).map((cadence) => <label key={cadence}><input type="radio" name="cadence" value={cadence} defaultChecked={profile.notification_cadence === cadence} /><span><strong>{cadence === "instant" ? "Instant" : cadence === "hourly" ? "Hourly" : "Daily"}</strong><small>{cadence === "instant" ? "As soon as it matches" : cadence === "hourly" ? "One compact digest" : "One daily roundup"}</small></span></label>)}</div></section>

      <section className="preference-section preference-section--compact"><div className="preference-heading"><span>03</span><div><h2>Local time</h2><p>Used to schedule hourly and daily digests correctly.</p></div></div><div className="field timezone-field"><label htmlFor="timezone">Timezone</label><input id="timezone" name="timezone" defaultValue={profile.timezone} required /><span className="field__help">IANA format, for example America/Toronto.</span></div></section>
      <div className="settings-save"><p>Changes affect future delivery attempts.</p><button className="button button--primary" disabled={pending}>{pending && <LoaderCircle className="spin" size={18} />}Save preferences</button></div>
    </form>
  </div>;
}
